param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $Root "dist\windows\dependencies"
}

$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$ExpectedHash = "14B42DD9F4B4A7813A8BFD69C8F99316C2888CC4EE26F631F397E163D85D6C62"
$InstallerName = "basic-miktex-25.12-x64.exe"
$InstallerUrl = "https://miktex.org/download/ctan/systems/win32/miktex/setup/windows-x64/$InstallerName"
$InstallerPath = Join-Path $OutputRoot $InstallerName

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

if (-not (Test-Path -LiteralPath $InstallerPath)) {
    Write-Host "Downloading $InstallerName"
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $InstallerPath
}

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $InstallerPath).Hash.ToUpperInvariant()
if ($Hash -ne $ExpectedHash) {
    throw "Unexpected SHA256 for $InstallerPath. Expected $ExpectedHash, got $Hash."
}

$ReadmeSource = Join-Path $Root "third_party\report_dependencies\windows\README_REPORT_DEPENDENCIES_zh.md"
if (Test-Path -LiteralPath $ReadmeSource) {
    Copy-Item -LiteralPath $ReadmeSource -Destination (Join-Path $OutputRoot "README_REPORT_DEPENDENCIES_zh.md") -Force
}

Write-Host "Report dependency package is ready: $OutputRoot"
