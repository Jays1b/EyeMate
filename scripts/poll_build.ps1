# Wait for the WSL buildozer build started by scripts\build_android.ps1
# and copy any produced APK/AAB back into .\bin\.
param(
    [string]$Distro = "Ubuntu-24.04",
    [int]$TimeoutMinutes = 180
)

$ErrorActionPreference = "Stop"
$Project = (Resolve-Path ".").Path
$Bin = Join-Path $Project "bin"
$WslLog = "/root/eyemate-src/build.log"

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
Write-Host "Waiting for build to finish (up to $TimeoutMinutes min)." -ForegroundColor Yellow

while ((Get-Date) -lt $deadline) {
    $running = wsl -d $Distro -- sh -c "pgrep -f buildozer >/dev/null 2>&1 && echo yes || echo no"
    if ($running.Trim() -eq "no") {
        Write-Host "Build process finished." -ForegroundColor Green
        break
    }
    Start-Sleep -Seconds 20
}

if ((Get-Date) -ge $deadline) {
    Write-Host "Timed out. Build still running? Check:" -ForegroundColor Red
    Write-Host "  wsl -d $Distro -- tail -n 50 /root/eyemate-src/build.log"
    Write-Host "  wsl -d $Distro -- pgrep -af buildozer"
    exit 1
}

Write-Host "--- Last 30 lines of build log ---" -ForegroundColor Cyan
wsl -d $Distro -- sh -c "tail -n 30 $WslLog"

$built = wsl -d $Distro -- sh -c "ls $WslBin/*.apk $WslBin/*.aab 2>/dev/null | head -20"
if (-not $built) {
    Write-Host "No APK/AAB produced. Build may have failed." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $Bin | Out-Null
wsl -d $Distro -- sh -c "cp $WslBin/*.apk $WslBin/*.aab /mnt/c/Users/UBITHEGREAT/Documents/EyeMate/bin/ 2>/dev/null"
Write-Host "Artifacts copied to .\bin\" -ForegroundColor Green
Get-ChildItem $Bin | Select-Object Name, Length