# EyeMate

EyeMate is an offline-first assistive vision companion for Android and Windows. It combines camera-based scene understanding, color identification, barcode reading, OCR, clipboard reading, and spoken feedback in a high-contrast Kivy interface.

[![Build Android APK](https://github.com/Jays1b/EyeMate/actions/workflows/build-android.yml/badge.svg)](https://github.com/Jays1b/EyeMate/actions/workflows/build-android.yml)

## Features

- Scene and object description with an ONNX detector
- Color identification from the camera view
- QR and barcode scanning
- OCR with graceful fallback when Tesseract is unavailable
- Android text-to-speech and speech recognition
- Desktop debugging through typed commands
- Offline runtime design with no cloud service required

## Run On Windows

Use the included debug launcher from the repository root:

```powershell
.\run_debug.ps1
```

For a fresh virtual environment:

```powershell
.\run_debug.ps1 -InstallDependencies
```

The launcher runs the tests before starting the Kivy application. See [DEBUGGING.md](DEBUGGING.md) for troubleshooting.

## Build The Android APK

The canonical Android source is the repository root. GitHub Actions builds the debug APK on every `v*` tag:

1. Open [Actions](https://github.com/Jays1b/EyeMate/actions).
2. Open the latest **Build Android APK** run.
3. Download the `EyeMate-debug-apk` artifact, or download the APK from the GitHub Release created for the tag.

The build uses Python 3.11, Android API 35, NDK 28c, arm64-v8a, Buildozer master, and the CameraX provider required by Camera4Kivy.

For a local WSL build, see [BUILD_ANDROID.md](BUILD_ANDROID.md).

## Install A Debug APK

Enable Developer options and USB debugging, then run:

```powershell
adb install -r bin\eyemate-0.1-*-arm64-v8a*.apk
```

## Known Limitations

- Screen OCR requires a native Tesseract installation on desktop. Android reports a graceful unavailable message.
- Camera and speech features require the relevant Windows or Android permissions.
- The Android build currently targets 64-bit arm64-v8a devices.

## Project Layout

- `main.py` and `main.kv`: application entry point and interface
- `services/`: vision, color, barcode, OCR, speech, and command services
- `models/`: on-device detection models and labels
- `buildozer.spec`: Android package configuration
- `.github/workflows/build-android.yml`: reproducible APK build and release workflow

## License

No license has been selected for this project yet.
