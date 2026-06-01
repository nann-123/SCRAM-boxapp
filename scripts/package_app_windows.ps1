param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RootFull = [System.IO.Path]::GetFullPath($Root)
$AppName = "SCRAM BoxApp"
$PackageId = "SCRAMBoxApp"
$Version = "0.1.0"
$Arch = "windows-x64"

Set-Location $RootFull

function Get-FullPath([string]$Path) {
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-InsideRoot([string]$Path) {
    $Full = Get-FullPath $Path
    $RootPrefix = $RootFull.TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $Full.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to write outside repository root: $Full"
    }
    return $Full
}

function Reset-Directory([string]$Path) {
    $Full = Assert-InsideRoot $Path
    if (Test-Path -LiteralPath $Full) {
        Remove-Item -LiteralPath $Full -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Full -Force | Out-Null
    return $Full
}

function Find-BootstrapPython {
    if ($env:SCRAM_PYTHON) {
        return $env:SCRAM_PYTHON
    }
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if ($Python) {
        return $Python.Source
    }
    $Py = Get-Command py -ErrorAction SilentlyContinue
    if ($Py) {
        return $Py.Source
    }
    throw "No Python interpreter was found. Install Python 3.10+ or set SCRAM_PYTHON."
}

function Find-CSharpCompiler {
    $Csc = Get-Command csc.exe -ErrorAction SilentlyContinue
    if ($Csc) {
        return $Csc.Source
    }
    $Candidates = @(
        "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate) {
            return $Candidate
        }
    }
    throw "No C# compiler was found. Install .NET Framework build tools or use the portable zip."
}

$VenvDir = Join-Path $RootFull ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    $BootstrapPython = Find-BootstrapPython
    & $BootstrapPython -m venv $VenvDir
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $RootFull "requirements.txt") pyinstaller

$BuildRoot = Join-Path $RootFull "build\windows"
$DistRoot = Join-Path $RootFull "dist\windows"
$RuntimePayloadRoot = Join-Path $BuildRoot "runtime_payload"
$RuntimePayload = Join-Path $RuntimePayloadRoot "core\executables_or_wrappers\runtime\windows"
$PyInstallerWork = Join-Path $BuildRoot "pyinstaller"
$SpecRoot = Join-Path $BuildRoot "spec"

Reset-Directory $BuildRoot | Out-Null
Reset-Directory $DistRoot | Out-Null
New-Item -ItemType Directory -Path $RuntimePayload -Force | Out-Null
New-Item -ItemType Directory -Path $PyInstallerWork -Force | Out-Null
New-Item -ItemType Directory -Path $SpecRoot -Force | Out-Null

$RuntimeSource = Join-Path $RootFull "core\executables_or_wrappers\runtime\windows"
if (-not (Test-Path -LiteralPath (Join-Path $RuntimeSource "ProgramSCRAM.exe"))) {
    throw "ProgramSCRAM.exe is missing from $RuntimeSource. Build the Windows SCRAM runtime first."
}

$ExcludedRuntimeItems = @(".venv", ".conda-scram-build", "source", "RESULT", "results", "__pycache__")
Get-ChildItem -LiteralPath $RuntimeSource -Force | Where-Object {
    $ExcludedRuntimeItems -notcontains $_.Name
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $RuntimePayload -Recurse -Force
}

$AddData = @(
    "$RuntimePayload;core/executables_or_wrappers/runtime/windows",
    "$(Join-Path $RootFull 'app\i18n');app/i18n",
    "$(Join-Path $RootFull 'app\resources');app/resources",
    "$(Join-Path $RootFull 'core\defaults');core/defaults",
    "$(Join-Path $RootFull 'core\schema');core/schema",
    "$(Join-Path $RootFull 'core\templates');core/templates",
    "$(Join-Path $RootFull 'docs\screenshots');docs/screenshots"
)

$PyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--name", $AppName,
    "--windowed",
    "--distpath", $DistRoot,
    "--workpath", $PyInstallerWork,
    "--specpath", $SpecRoot,
    "--hidden-import", "PySide6.QtSvg",
    "--collect-data", "matplotlib"
)
foreach ($Item in $AddData) {
    $PyInstallerArgs += @("--add-data", $Item)
}
$PyInstallerArgs += "app\main.py"

& $VenvPython -m PyInstaller @PyInstallerArgs

$AppDir = Join-Path $DistRoot $AppName
$AppExe = Join-Path $AppDir "$AppName.exe"
if (-not (Test-Path -LiteralPath $AppExe)) {
    throw "Packaged GUI executable was not created: $AppExe"
}

$VersionText = @"
$AppName $Version

Start the GUI by double-clicking "$AppName.exe".
The bundled ProgramSCRAM.exe is the command-line simulation core and is not the GUI entry point.
PDF reports work without LaTeX through the built-in offline backend. Optional LaTeX installers are in report_dependencies.
The Chinese user manual is in docs.
"@
Set-Content -LiteralPath (Join-Path $AppDir "README_FIRST.txt") -Value $VersionText -Encoding UTF8

$AppDocsDir = Join-Path $AppDir "docs"
New-Item -ItemType Directory -Path $AppDocsDir -Force | Out-Null
$ManualPatterns = @(
    "docs\SCRAM_BoxApp_*",
    "docs\report_dependencies_windows.md",
    "docs\validation_checklist.md"
)
foreach ($ManualPattern in $ManualPatterns) {
    $ManualPath = Join-Path $RootFull $ManualPattern
    if (Test-Path -Path $ManualPath) {
        Copy-Item -Path $ManualPath -Destination $AppDocsDir -Force
    }
}

$DependencySource = Join-Path $RootFull "third_party\report_dependencies\windows"
if (Test-Path -LiteralPath $DependencySource) {
    $AppDependencyDir = Join-Path $AppDir "report_dependencies"
    $DistDependencyDir = Join-Path $DistRoot "dependencies"
    New-Item -ItemType Directory -Path $AppDependencyDir -Force | Out-Null
    New-Item -ItemType Directory -Path $DistDependencyDir -Force | Out-Null
    Copy-Item -Path (Join-Path $DependencySource "*") -Destination $AppDependencyDir -Recurse -Force
    Copy-Item -Path (Join-Path $DependencySource "*") -Destination $DistDependencyDir -Recurse -Force
}

$ZipPath = Join-Path $DistRoot "$PackageId-$Arch.zip"
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $AppDir "*") -DestinationPath $ZipPath -Force

if (-not $SkipInstaller) {
    $InstallerBuildDir = Reset-Directory (Join-Path $BuildRoot "installer")
    $InstallerSource = Join-Path $InstallerBuildDir "ScramBoxAppInstaller.cs"
    $InstallerPath = Join-Path $DistRoot "$PackageId-Setup-$Arch.exe"
    $InstallerCode = @'
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class ScramBoxAppInstaller
{
    private const string AppName = "SCRAM BoxApp";
    private const string PackageId = "SCRAMBoxApp";
    private const string Version = "__APP_VERSION__";
    private const string PayloadResourceName = "SCRAMBoxAppPayload";

    [STAThread]
    private static int Main(string[] args)
    {
        bool quiet = false;
        foreach (string arg in args)
        {
            if (string.Equals(arg, "/quiet", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(arg, "-quiet", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(arg, "/q", StringComparison.OrdinalIgnoreCase))
            {
                quiet = true;
            }
        }

        try
        {
            Install(quiet);
            return 0;
        }
        catch (Exception ex)
        {
            if (quiet)
            {
                Console.Error.WriteLine(ex.ToString());
            }
            else
            {
                MessageBox.Show(ex.ToString(), AppName + " installer error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            return 1;
        }
    }

    private static void Install(bool quiet)
    {
        string installRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs",
            AppName);
        string appExe = Path.Combine(installRoot, AppName + ".exe");

        if (Directory.Exists(installRoot))
        {
            Directory.Delete(installRoot, true);
        }
        Directory.CreateDirectory(installRoot);

        string tempZip = Path.Combine(Path.GetTempPath(), PackageId + "-" + Guid.NewGuid().ToString("N") + ".zip");
        using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream(PayloadResourceName))
        {
            if (payload == null)
            {
                throw new InvalidOperationException("Installer payload resource is missing.");
            }
            using (FileStream file = File.Create(tempZip))
            {
                payload.CopyTo(file);
            }
        }

        ZipFile.ExtractToDirectory(tempZip, installRoot);
        File.Delete(tempZip);

        if (!File.Exists(appExe))
        {
            throw new FileNotFoundException("Installed GUI executable is missing.", appExe);
        }

        string programsDir = Environment.GetFolderPath(Environment.SpecialFolder.Programs);
        string startFolder = Path.Combine(programsDir, AppName);
        string startShortcut = Path.Combine(startFolder, AppName + ".lnk");
        string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        string desktopShortcut = Path.Combine(desktopDir, AppName + ".lnk");

        CreateShortcut(startShortcut, appExe, installRoot);
        if (!string.IsNullOrEmpty(desktopDir))
        {
            CreateShortcut(desktopShortcut, appExe, installRoot);
        }

        WriteUninstaller(installRoot, desktopShortcut, startShortcut, startFolder);
        WriteUninstallRegistry(installRoot, appExe);

        if (!quiet)
        {
            DialogResult result = MessageBox.Show(
                "Installation complete. Start SCRAM BoxApp now?",
                AppName,
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Information);
            if (result == DialogResult.Yes)
            {
                Process.Start(appExe);
            }
        }
    }

    private static void CreateShortcut(string shortcutPath, string targetPath, string workingDirectory)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(shortcutPath));
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null)
        {
            return;
        }
        object shell = Activator.CreateInstance(shellType);
        object shortcut = null;
        try
        {
            shortcut = shellType.InvokeMember(
                "CreateShortcut",
                System.Reflection.BindingFlags.InvokeMethod,
                null,
                shell,
                new object[] { shortcutPath });
            Type shortcutType = shortcut.GetType();
            shortcutType.InvokeMember("TargetPath", System.Reflection.BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
            shortcutType.InvokeMember("WorkingDirectory", System.Reflection.BindingFlags.SetProperty, null, shortcut, new object[] { workingDirectory });
            shortcutType.InvokeMember("IconLocation", System.Reflection.BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
            shortcutType.InvokeMember("Description", System.Reflection.BindingFlags.SetProperty, null, shortcut, new object[] { "SCRAM BoxApp GUI" });
            shortcutType.InvokeMember("Save", System.Reflection.BindingFlags.InvokeMethod, null, shortcut, null);
        }
        finally
        {
            if (shortcut != null && Marshal.IsComObject(shortcut))
            {
                Marshal.FinalReleaseComObject(shortcut);
            }
            if (shell != null && Marshal.IsComObject(shell))
            {
                Marshal.FinalReleaseComObject(shell);
            }
        }
    }

    private static void WriteUninstaller(string installRoot, string desktopShortcut, string startShortcut, string startFolder)
    {
        string uninstallPs1 = Path.Combine(installRoot, "uninstall.ps1");
        string content =
            "$ErrorActionPreference = 'SilentlyContinue'\r\n" +
            "Remove-Item -LiteralPath " + PowerShellLiteral(desktopShortcut) + " -Force\r\n" +
            "Remove-Item -LiteralPath " + PowerShellLiteral(startShortcut) + " -Force\r\n" +
            "Remove-Item -LiteralPath " + PowerShellLiteral(startFolder) + " -Recurse -Force\r\n" +
            "Remove-Item -LiteralPath 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" + PackageId + "' -Recurse -Force\r\n" +
            "Start-Sleep -Milliseconds 300\r\n" +
            "Remove-Item -LiteralPath " + PowerShellLiteral(installRoot) + " -Recurse -Force\r\n";
        File.WriteAllText(uninstallPs1, content);

        string uninstallCmd = Path.Combine(installRoot, "Uninstall SCRAM BoxApp.cmd");
        string cmd = "@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File " + CommandQuote(uninstallPs1) + "\r\n";
        File.WriteAllText(uninstallCmd, cmd);
    }

    private static void WriteUninstallRegistry(string installRoot, string appExe)
    {
        using (RegistryKey key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\" + PackageId))
        {
            if (key == null)
            {
                return;
            }
            string uninstallPs1 = Path.Combine(installRoot, "uninstall.ps1");
            key.SetValue("DisplayName", AppName, RegistryValueKind.String);
            key.SetValue("DisplayVersion", Version, RegistryValueKind.String);
            key.SetValue("Publisher", "SCRAM BoxApp", RegistryValueKind.String);
            key.SetValue("InstallLocation", installRoot, RegistryValueKind.String);
            key.SetValue("DisplayIcon", appExe, RegistryValueKind.String);
            key.SetValue("UninstallString", "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " + CommandQuote(uninstallPs1), RegistryValueKind.String);
            key.SetValue("NoModify", 1, RegistryValueKind.DWord);
            key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
        }
    }

    private static string PowerShellLiteral(string value)
    {
        return "'" + value.Replace("'", "''") + "'";
    }

    private static string CommandQuote(string value)
    {
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }
}
'@
    $InstallerCode = $InstallerCode.Replace("__APP_VERSION__", $Version)
    Set-Content -LiteralPath $InstallerSource -Value $InstallerCode -Encoding UTF8

    $Csc = Find-CSharpCompiler
    & $Csc `
        /nologo `
        /target:winexe `
        /platform:x64 `
        /out:$InstallerPath `
        "/resource:$ZipPath,SCRAMBoxAppPayload" `
        /reference:System.Windows.Forms.dll `
        /reference:System.IO.Compression.dll `
        /reference:System.IO.Compression.FileSystem.dll `
        $InstallerSource
    if ($LASTEXITCODE -ne 0) {
        throw "C# installer compilation failed."
    }
    if (-not (Test-Path -LiteralPath $InstallerPath)) {
        throw "Installer was not created: $InstallerPath"
    }
}

Write-Host "Packaged app: $AppExe"
Write-Host "Portable zip: $ZipPath"
if (-not $SkipInstaller) {
    Write-Host "Installer: $(Join-Path $DistRoot "$PackageId-Setup-$Arch.exe")"
}
