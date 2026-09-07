# Building the Android APK

Two supported routes — pick whichever you can run:

## Option A — GitHub Actions (no local Android toolchain needed)

The project ships a prebuilt workflow at `.github/workflows/build-android.yml`.

1. Create a repo (e.g. `EyeMate`) at https://github.com/new and push the project:
   ```
   git init
   git add -A && git commit -m "EyeMate: vision + voice assistant for Android"
   git branch -M main
   git remote add origin https://github.com/<you>/EyeMate.git
   git push -u origin main
   ```
2. On GitHub: **Actions** → **Build Android APK** → **Run workflow** (or push a `v*` tag).
3. When the job finishes, the APK is in the **Artifacts** section of the run
   (`EyeMate-debug-apk`).

Notes:
- The first build takes ~30–60 min (compiles `opencv`, `camera4kivy`, `libzbar`
  from source). Later runs use the `.buildozer` cache.
- No secrets/keys are required for the debug APK.

## Option B — local WSL build (Windows, no Docker)

1. Enable WSL and install Ubuntu 24.04 if needed:
   ```
   wsl --install -d Ubuntu
   ```
   (Reboot if prompted. Admin rights are required only for enabling the WSL
   Windows feature, not for building.)
2. From the project folder run:
   ```
   powershell -ExecutionPolicy Bypass -File scripts\build_android.ps1
   ```
   The script downloads the Ubuntu rootfs if no distro exists, installs the
   build tools and master buildozer inside WSL, builds the debug APK, and
   copies it to `.\bin\`.

## Installing on a device

Enable **Developer options** and **USB debugging** on the phone, then:

```
adb install -r bin\eyemate-0.1-*-arm64-v8a*.apk
```

## What gets built

| Component                | Desktop (Windows)               | Android APK                          |
|--------------------------|---------------------------------|--------------------------------------|
| Camera/Screen link       | OpenCV `cv2.VideoCapture(0)`    | Camera4Kivy `Camera` widget          |
| Object detection         | TFLite `ssd_mobilenet_v2`       | OpenCV DNN + `models/yolo11n.onnx`   |
| Speech recognition       | SAPI (`sr.Recognizer`)          | SpeechRecognizer (via pyjnius)       |
| Text-to-speech           | SAPI                             | Android TTS                          |
| Speech -> command voice  | Kivy `TextInput` tick            | Android voice view                    |
| On-device OCR (screen)   | pytesseract + system tesseract  | degrades to "OCR unavailable" notice |

## Known limitations

- Screen-text OCR needs a native tesseract binary, which python-for-android
  does not bundle, so the Android build reports that OCR is unavailable.
  Detection, QR/barcode reading, object (YOLO) detection and all voice/UI
  features do work.
- The APK source is the repository root. `_wsl_staging`, IDE files, tests,
   build caches, and unrelated folders are excluded by `buildozer.spec`.
- Camera preview is opened only when reaching a camera-connected screen; you
   may need to tap the shutter/auto modes to wake the Android `Camera`.