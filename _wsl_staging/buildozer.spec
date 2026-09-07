[app]

# (str) Application name
title = EyeMate

# (str) Package name
package.name = eyemate

# (str) Package domain (needs to be unique)
package.domain = org.eyemate

# (str) Application version
version = 0.1

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (relative to source.dir)
source.include_exts = py, kv, txt, tflite, onnx, ini, png, jpg

# (list) Application requirements
# Camera4Kivy needs the 'master' Buildozer (>=1.2.0.dev0):
#   pip3 install git+https://github.com/kivy/buildozer.git
# pyjnius is added automatically by the sdl2 bootstrap for TTS/STT.
# 'opencv' and 'numpy' provide color + QR decode and the object detector
# (cv2.dnn loads models/yolo11n.onnx — works on Android, no TFLite wheel
# needed; the app degrades gracefully when detection is unavailable).
# 'libzbar' backs pyzbar for 1D barcodes.
requirements = python3,kivy>=2.3.0,camera4kivy,opencv,numpy,libzbar

# (bool) Accept the Android SDK / AndroidX licenses automatically.
android.accept_sdk_license = True

# (str) CameraX provider for Camera4Kivy (on Android).
# Run once before building on a fresh checkout:
#   git clone https://github.com/Android-for-Python/camerax_provider.git
#   rm -rf camerax_provider/.git
# The hook sets enable_androidx, CAMERA+RECORD_AUDIO permissions, the CameraX
# gradle dependencies, and android.add_src = camerax_provider/camerax_src.
p4a.hook = camerax_provider

# (str) Android permissions
android.permissions = CAMERA, RECORD_AUDIO

# (int) Android API level to target
android.api = 33

# (int) Minimum API level (CameraX requires >= 21)
android.minapi = 21

# (str) Android architecture(s).
# NOTE: CameraX gradle deps are ABI-specific; build matching archs only.
# 64-bit only: modern phones; halves first-build compile time (opencv builds
# from source). Re-add armeabi-v7a only if you must support old 32-bit devices.
android.archs = arm64-v8a

# (str) Package format for debug releases (adb install).
android.debug_artifact = apk

# (str) Package format for release builds. Google Play requires an Android
# App Bundle (AAB), which you upload to the Play Console.
android.release_artifact = aab

# (str) Orientation
orientation = portrait

# (bool) Keep the presplash screen color simple (dark)
android.presplash_color = #080F1E

# (str) Icon of the application (512x512 PNG, used for Google Play Store and general icon)
icon.filename = %(source.dir)s/assets/icon.png

# (str) Adaptive icon of the application (used if Android API level is 26+ at runtime)
icon.adaptive_foreground.filename = %(source.dir)s/assets/icon_fg.png
icon.adaptive_background.filename = %(source.dir)s/assets/icon_bg.png

# (str) Presplash / splash screen of the application
presplash.filename = %(source.dir)s/assets/presplash.png

# (str) Release signing for Google Play.
# Buildozer signs the release build with the Android SDK debug key by default.
# To sign with your own release keystore, set ALL four environment variables
# before running `buildozer android release`, for example in WSL:
#   export P4A_RELEASE_KEYSTORE=$(pwd)/keystore/eyemate-release.keystore
#   export P4A_RELEASE_KEYSTORE_PASSWD=<store password>
#   export P4A_RELEASE_KEYALIAS=eyemate
#   export P4A_RELEASE_KEYALIAS_PASSWD=<key password>
# Without them the AAB is produced unsigned (*-release-unsigned.aab).
# Back up keystore/ — if you lose it you cannot update the app on Google Play.
# On GitHub Actions, set the same variables from repository Secrets.

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2