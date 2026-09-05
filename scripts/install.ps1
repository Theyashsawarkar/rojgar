# Sets up the venv, installs rojgar into it, and puts a `rojgar.bat`
# shim on your PATH so it works from any terminal without activating
# the venv or typing its path every time.
#
# Run from PowerShell:  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $ProjectRoot ".venv"

if (-not (Test-Path $Venv)) {
    Write-Host "Creating virtual environment..."
    python -m venv $Venv
}

Write-Host "Installing dependencies..."
& "$Venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& "$Venv\Scripts\pip.exe" install --quiet -e $ProjectRoot

$BinDir = Join-Path $env:USERPROFILE "bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$ShimPath = Join-Path $BinDir "rojgar.bat"
$RojgarExe = Join-Path $Venv "Scripts\rojgar.exe"
Set-Content -Path $ShimPath -Encoding ASCII -Value "@echo off`r`n`"$RojgarExe`" %*"

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "Added $BinDir to your PATH."
    Write-Host "Open a NEW terminal window for this to take effect (PATH changes"
    Write-Host "aren't picked up by terminals already open)."
} else {
    Write-Host "Done."
}

Write-Host "Then try: rojgar --help"
