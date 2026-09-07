param(
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$pythonCandidates = @(
    ".venv-1\Scripts\python.exe",
    ".venv\Scripts\python.exe",
    "python"
)
$python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq "python" -or (Test-Path $candidate)) {
        try {
            & $candidate --version *> $null
            if ($LASTEXITCODE -eq 0) {
                $python = $candidate
                break
            }
        } catch {
            continue
        }
    }
}

if ($null -eq $python) {
    throw "Python was not found. Create .venv-1 or install Python, then run this script again."
}

if ($InstallDependencies) {
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed."
    }
}

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) {
    throw "Tests failed. Fix the reported failure before starting the app."
}

Write-Host "Starting EyeMate from the repository root..." -ForegroundColor Cyan
& $python main.py
exit $LASTEXITCODE