# Build the EyeMate debug APK inside WSL Ubuntu (no Docker required).
# Requires: WSL enabled and a Windows host with internet access.
#
# Usage (PowerShell, from the project folder):
#   powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1
#
# Steps taken:
#   1. Ensure WSL2 and an Ubuntu distro (installs 'eyemate-build' if none).
#   2. Sync this project to the WSL home (avoids the slow /mnt/c filesystem).
#   3. Install Linux deps + master buildozer inside WSL.
#   4. Clone camerax_provider and run `buildozer android debug`.
#   5. Copy bin/*.apk back into .\bin\.
param(
    [string]$Distro = "Ubuntu-24.04"
)

$ErrorActionPreference = "Stop"
$Project = (Resolve-Path ".").Path
$Bin = Join-Path $Project "bin"
$Staging = Join-Path $Project "_wsl_staging"

wsl --status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "WSL is not enabled. Run:  wsl --install  then reboot." -ForegroundColor Red
    exit 1
}

$hasDistro = (wsl -l -q | ForEach-Object { $_.Trim() } | Where-Object { $_ -eq $Distro }) -ne $null
if (-not $hasDistro) {
    Write-Host "No '$Distro' distro found. Installing Ubuntu..." -ForegroundColor Yellow
    wsl --install -d Ubuntu-24.04
    if ($LASTEXITCODE -ne 0) { Write-Host "Distro install failed." -ForegroundColor Red; exit 1 }
    wsl -d $Distro -- sh -c "apt-get update && apt-get install -y ca-certificates"
}

Write-Host "Staging project files (excluding venv/git/caches)..." -ForegroundColor Yellow
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Force -Path $Staging | Out-Null
Get-ChildItem $Project -Force | Where-Object {
    $_.Name -notin @(".venv", ".git", "bin", ".pytest_cache", "__pycache__", "_wsl_staging")
} | ForEach-Object {
    Copy-Item -Recurse $_.FullName $Staging
}

wsl -d $Distro -- sh -c "rm -rf ~/eyemate-src/project && mkdir -p ~/eyemate-src/project"
wsl -d $Distro -- sh -c "cp -r /mnt/c/Users/UBITHEGREAT/Documents/EyeMate/_wsl_staging/. ~/eyemate-src/project/"

Write-Host "Installing build toolchain (first run takes a while)..." -ForegroundColor Yellow
wsl -d $Distro -- bash -c @"
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends git zip unzip openjdk-17-jdk \
  autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
  libtinfo6 cmake libffi-dev libssl-dev python3 python3-pip
pip3 install git+https://github.com/kivy/buildozer.git --break-system-packages
cd ~/eyemate-src/project
if [ ! -d camerax_provider ]; then git clone --depth 1 https://github.com/inclement/camerax_provider.git; fi
buildozer -v android debug
"@

if ($LASTEXITCODE -ne 0) { Write-Host "Build failed inside WSL." -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Force -Path $Bin | Out-Null
wsl -d $Distro -- sh -c "cp ~/eyemate-src/project/bin/*.apk /mnt/c/Users/UBITHEGREAT/Documents/EyeMate/bin/ 2>/dev/null"
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
Write-Host "APK ready in .\bin\ (to sideload: adb install -r bin\*.apk)" -ForegroundColor Green