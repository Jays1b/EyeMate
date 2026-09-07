# Running EyeMate for debugging

Open PowerShell in the root `EyeMate` folder and run:

```powershell
.\run_debug.ps1
```

The launcher uses `.venv-1` first, then `.venv`, then `python` on `PATH`. It
runs the tests before starting `main.py`, so a dependency or code problem is
reported before the Kivy window opens.

For a fresh environment, install dependencies first:

```powershell
.\run_debug.ps1 -InstallDependencies
```

The desktop app can run without a camera. Camera actions will announce that
the camera is unavailable, while text, clipboard, help, and typed commands
remain usable.

To run the tests only:

```powershell
.\.venv-1\Scripts\python.exe -m pytest -q
```
