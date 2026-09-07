# Build the EyeMate APK inside WSL Ubuntu (no Docker required).
# Requires: WSL enabled and a Windows host with internet access.
#
# Usage (PowerShell, from the project folder):
#   powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1
#
# What this does:
#   1. Ensure WSL2 and an Ubuntu distro (installs 'Ubuntu-24.04' if none).
#   2. Sync this project to the WSL home (keeps the ~/.buildozer cache so
#      repeat builds are fast; the Android SDK/NDK only download once).
#   3. Install Linux deps + master buildozer inside WSL (idempotent).
#   4. Clone camerax_provider and run `buildozer android debug`.
#   5. Copy bin/*.apk back into .\bin\.
param(
    [string]$Distro = "Ubuntu-24.04",
    [switch]$Release
)

$ErrorActionPreference = "Stop"
$Project = (Resolve-Path ".").Path
$Bin = Join-Path $Project "bin"
$Staging = Join-Path $Project "_wsl_staging"
$WslProject = "/root/eyemate-src/project"
$WslBin = "/root/eyemate-src/project/bin"
$WinBin = (($Bin -replace '^([A-Za-z]):\\', '/mnt/$1/') -replace '\\', '/')

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
}



Write-Host "Staging project files (excluding venv/git/caches)..." -ForegroundColor Yellow
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Force -Path $Staging | Out-Null
Get-ChildItem $Project -Force | Where-Object {
    $_.Name -notin @(".venv", ".git", "bin", ".pytest_cache", "__pycache__", "_wsl_staging", ".buildozer")
} | ForEach-Object {
    Copy-Item -Recurse $_.FullName $Staging
}

# Overlay files into the persistent WSL project. Never delete the WSL project
# dir: that would destroy the .buildozer cache (SDK/NDK/dist) and force a
# multi-hour rebuild every time.
wsl -d $Distro -u root -- sh -c "mkdir -p $WslProject && cp -r /mnt/c/Users/UBITHEGREAT/Documents/EyeMate/_wsl_staging/. $WslProject/"

if ($Release) {
    Write-Host "Release build requested." -ForegroundColor Yellow
    wsl -d $Distro -u root -- sh -c "ls $WslProject/keystore/eyemate-release.keystore >/dev/null 2>&1 || echo 'WARNING: keystore not synced - release will be unsigned'"
}

Write-Host "Installing build toolchain (idempotent)..." -ForegroundColor Yellow
wsl -d $Distro -u root -- bash -c @"
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends git zip unzip openjdk-17-jdk \
  autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
  libtinfo6 cmake libffi-dev libssl-dev python3 python3-pip >/dev/null

# Install master buildozer only when missing (checked via pip show).
if ! python3 -c 'import buildozer' 2>/dev/null; then
  echo 'Installing master buildozer...'
  pip3 install git+https://github.com/kivy/buildozer.git --break-system-packages
fi
"@
if ($LASTEXITCODE -ne 0) { Write-Host "Toolchain install failed." -ForegroundColor Red; exit 1 }

Write-Host "Starting buildozer build (detached, logging to WSL /root/eyemate-src/build.log)..." -ForegroundColor Yellow
$buildCmd = "buildozer android debug"
if ($Release) { $buildCmd = "buildozer android release" }

wsl -d $Distro -u root -- sh -c "cd $WslProject && if [ ! -d camerax_provider ]; then git clone --depth 1 https://github.com/Android-for-Python/camerax_provider.git; fi && rm -f /root/eyemate-src/build.log && nohup sh -c 'cd $WslProject && $buildCmd' > /root/eyemate-src/build.log 2>&1 & echo started"

Write-Host "Build started in the background. Poll progress with:" -ForegroundColor Green
Write-Host "  wsl -d $Distro -u root -- tail -f /root/eyemate-src/build.log" -ForegroundColor Cyan
Write-Host "Run scripts\poll_build.ps1 to wait for it and copy the APK back." -ForegroundColor Cyan
