# Build the mod and pack it as a drag-and-drop zip (SPT_Runtime/user/mods/<mod>).
# usage: powershell -File tools\package.ps1 [-Spt C:\SPT\SPT_Runtime] [-Version 0.3.0]
param(
    [string]$Spt = "C:\SPT\SPT_Runtime",
    [string]$Version = "0.3.0"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
$modName = "ShinnisQuestsBackport"
$dist = Join-Path $root "dist"
$modDir = Join-Path $dist "SPT_Runtime\user\mods\$modName"

dotnet build (Join-Path $root "src") -c Release -nologo -v q
if ($LASTEXITCODE) { throw "dotnet build failed" }

if (Test-Path $modDir) { Remove-Item -Recurse -Force $modDir }
New-Item -ItemType Directory -Force $modDir | Out-Null
python -X utf8 (Join-Path $root "tools\build.py") (Join-Path $root "data") (Join-Path $Spt "SPT_Data\database") $modDir
if ($LASTEXITCODE) { throw "build.py failed" }
Copy-Item (Join-Path $root "src\bin\Release\$modName.dll") $modDir
Copy-Item (Join-Path $root "src\config.json") $modDir
Move-Item (Join-Path $modDir "build_report.json") (Join-Path $dist "build_report.json") -Force

$zip = Join-Path $dist "$modName-$Version.zip"
if (Test-Path $zip) { Remove-Item $zip }
# tar.exe (bsdtar, ships with Windows) writes "/" separators; Compress-Archive on PS 5.1 writes "\" and breaks Linux servers
Push-Location $dist; tar.exe -a -c -f $zip SPT_Runtime; Pop-Location
if ($LASTEXITCODE) { throw "zip failed" }
"packed $zip"
