param(
    [switch]$SkipReportDependencies
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RootFull = [System.IO.Path]::GetFullPath($Root)
$OutRoot = Join-Path $RootFull "dist\win-devkit"
$PackageName = "SCRAMBoxApp-WinDevKit"
$PackageDir = Join-Path $OutRoot $PackageName
$ZipPath = Join-Path $OutRoot "$PackageName.zip"

Set-Location $RootFull

function Get-FullPath([string]$Path) {
    return [System.IO.Path]::GetFullPath($Path)
}

function Assert-InsideRoot([string]$Path) {
    $Full = Get-FullPath $Path
    $RootPrefix = $RootFull.TrimEnd([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)) + [System.IO.Path]::DirectorySeparatorChar
    if ($Full -eq $RootFull -or -not $Full.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
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

function Copy-FileIfPresent([string]$Source, [string]$DestinationDir) {
    if (Test-Path -LiteralPath $Source) {
        New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null
        Copy-Item -LiteralPath $Source -Destination $DestinationDir -Force
    }
}

function Copy-TreeRobocopy(
    [string]$Source,
    [string]$Destination,
    [string[]]$ExcludeDirs = @(),
    [string[]]$ExcludeFiles = @()
) {
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Required source directory is missing: $Source"
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $Args = @($Source, $Destination, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
    if ($ExcludeDirs.Count -gt 0) {
        $Args += "/XD"
        $Args += $ExcludeDirs
    }
    if ($ExcludeFiles.Count -gt 0) {
        $Args += "/XF"
        $Args += $ExcludeFiles
    }
    & robocopy @Args | Out-Null
    $Code = $LASTEXITCODE
    if ($Code -gt 7) {
        throw "robocopy failed from $Source to $Destination with exit code $Code"
    }
    $global:LASTEXITCODE = 0
}

function Write-Utf8BomFile([string]$DestinationFile, [string]$Text) {
    $Encoding = New-Object System.Text.UTF8Encoding -ArgumentList $true
    [System.IO.File]::WriteAllText($DestinationFile, $Text, $Encoding)
}

function Write-DevkitReadme([string]$DestinationFile) {
    $TemplatePath = Join-Path $RootFull "docs\windows_devkit_readme_zh.md"
    if (-not (Test-Path -LiteralPath $TemplatePath)) {
        throw "Missing README template: $TemplatePath"
    }
    $Text = [System.IO.File]::ReadAllText($TemplatePath, [System.Text.Encoding]::UTF8)
    Write-Utf8BomFile $DestinationFile $Text
}

$CommonExcludeDirs = @("__pycache__", ".pytest_cache")
$CommonExcludeFiles = @("*.pyc", "*.pyo")

Reset-Directory $OutRoot | Out-Null
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

foreach ($FileName in @("README.md", "requirements.txt", "pyproject.toml", ".gitignore")) {
    Copy-FileIfPresent (Join-Path $RootFull $FileName) $PackageDir
}

Copy-TreeRobocopy (Join-Path $RootFull "app") (Join-Path $PackageDir "app") $CommonExcludeDirs $CommonExcludeFiles
Copy-TreeRobocopy (Join-Path $RootFull "examples") (Join-Path $PackageDir "examples") $CommonExcludeDirs $CommonExcludeFiles

$CorePackageRoot = Join-Path $PackageDir "core"
Copy-TreeRobocopy (Join-Path $RootFull "core\defaults") (Join-Path $CorePackageRoot "defaults") $CommonExcludeDirs $CommonExcludeFiles
Copy-TreeRobocopy (Join-Path $RootFull "core\schema") (Join-Path $CorePackageRoot "schema") $CommonExcludeDirs $CommonExcludeFiles
Copy-TreeRobocopy (Join-Path $RootFull "core\templates") (Join-Path $CorePackageRoot "templates") $CommonExcludeDirs $CommonExcludeFiles

$RuntimeSource = Join-Path $RootFull "core\executables_or_wrappers\runtime\windows"
$RuntimeDest = Join-Path $CorePackageRoot "executables_or_wrappers\runtime\windows"
if (-not (Test-Path -LiteralPath (Join-Path $RuntimeSource "ProgramSCRAM.exe"))) {
    throw "ProgramSCRAM.exe is missing from $RuntimeSource"
}
$RuntimeExcludeDirs = @(".venv", ".conda-scram-build", "RESULT", "results", "boxapp_cfg", "__pycache__", ".pytest_cache")
$RuntimeExcludeFiles = @("*.pyc", "*.pyo", "*.obj", "*.o", "*.mod", "*.smod", ".sconsign.dblite", "*.log", "*.stackdump")
Copy-TreeRobocopy $RuntimeSource $RuntimeDest $RuntimeExcludeDirs $RuntimeExcludeFiles

$ScriptsDest = Join-Path $PackageDir "scripts"
New-Item -ItemType Directory -Path $ScriptsDest -Force | Out-Null
$ScriptFiles = @(
    "run_app_windows.bat",
    "package_app_windows.ps1",
    "package_app_windows.bat",
    "run_standard_tests.py",
    "capture_screenshots.py",
    "fetch_report_dependencies_windows.ps1",
    "launch_app.py",
    "run_pipeline.py",
    "make_windows_devkit.ps1"
)
foreach ($ScriptFile in $ScriptFiles) {
    Copy-FileIfPresent (Join-Path $RootFull "scripts\$ScriptFile") $ScriptsDest
}

$DocsSource = Join-Path $RootFull "docs"
$DocsDest = Join-Path $PackageDir "docs"
New-Item -ItemType Directory -Path $DocsDest -Force | Out-Null
$DocNames = @(
    "config_mapping_spec.md",
    "demo_walkthrough.md",
    "gui_workflow.md",
    "report_dependencies_windows.md",
    "shared_runtime_layout.md",
    "validation_checklist.md",
    "windows_devkit_readme_zh.md"
)
foreach ($DocName in $DocNames) {
    Copy-FileIfPresent (Join-Path $DocsSource $DocName) $DocsDest
}
Get-ChildItem -LiteralPath $DocsSource -File | Where-Object {
    $_.Name -like "SCRAM_BoxApp_*" -or $_.Name -like "*yb_0516.pdf"
} | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $DocsDest -Force
}
foreach ($DocDir in @("screenshots", "user_manual_zh_assets", "undergrad_lab_assets")) {
    $Source = Join-Path $DocsSource $DocDir
    if (Test-Path -LiteralPath $Source) {
        Copy-TreeRobocopy $Source (Join-Path $DocsDest $DocDir) $CommonExcludeDirs $CommonExcludeFiles
    }
}

if (-not $SkipReportDependencies) {
    $ReportDepsSource = Join-Path $RootFull "third_party\report_dependencies\windows"
    if (Test-Path -LiteralPath $ReportDepsSource) {
        Copy-TreeRobocopy $ReportDepsSource (Join-Path $PackageDir "third_party\report_dependencies\windows") $CommonExcludeDirs $CommonExcludeFiles
    }
}

Write-DevkitReadme (Join-Path $PackageDir "WINDOWS_DEVKIT_README_zh.md")
$PackagedTemplate = Join-Path $DocsDest "windows_devkit_readme_zh.md"
if (Test-Path -LiteralPath $PackagedTemplate) {
    $TemplateText = [System.IO.File]::ReadAllText($PackagedTemplate, [System.Text.Encoding]::UTF8)
    Write-Utf8BomFile $PackagedTemplate $TemplateText
}

$ManifestPath = Join-Path $PackageDir "WINDOWS_DEVKIT_MANIFEST.txt"
$PackageFull = Get-FullPath $PackageDir
$Manifest = New-Object System.Collections.Generic.List[string]
$Manifest.Add("SCRAM BoxApp Windows DevKit manifest")
$Manifest.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')")
$Manifest.Add("Source root: $RootFull")
$Manifest.Add("Package root: $PackageFull")
$Manifest.Add("Report dependencies included: $(-not $SkipReportDependencies)")
$Manifest.Add("")
$Manifest.Add("Excluded runtime directories: $($RuntimeExcludeDirs -join ', ')")
$Manifest.Add("Excluded runtime files: $($RuntimeExcludeFiles -join ', ')")
$Manifest.Add("")
$Manifest.Add("Files:")
Get-ChildItem -LiteralPath $PackageDir -Recurse -File | Sort-Object FullName | ForEach-Object {
    $Relative = $_.FullName.Substring($PackageFull.Length).TrimStart([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
    $Manifest.Add("$Relative`t$($_.Length)")
}
Set-Content -LiteralPath $ManifestPath -Value $Manifest -Encoding UTF8

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath (Assert-InsideRoot $ZipPath) -Force
}
Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal -Force

$FileCount = (Get-ChildItem -LiteralPath $PackageDir -Recurse -File | Measure-Object).Count
$PackageSize = (Get-ChildItem -LiteralPath $PackageDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$ZipSize = (Get-Item -LiteralPath $ZipPath).Length

Write-Host "Windows development package created:"
Write-Host "  Folder: $PackageDir"
Write-Host "  Zip:    $ZipPath"
Write-Host "  Files:  $FileCount"
Write-Host ("  Folder size: {0:N1} MB" -f ($PackageSize / 1MB))
Write-Host ("  Zip size:    {0:N1} MB" -f ($ZipSize / 1MB))
