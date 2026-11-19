# One Hand Operation+ (Universal Android Port)

![Version](https://img.shields.io/badge/Base%20Version-9.4.23.0-blue?style=for-the-badge)
![Android](https://img.shields.io/badge/Android-14%20%E2%80%93%2016%2B-3DDC84?style=for-the-badge&logo=android&logoColor=white)
![Root](https://img.shields.io/badge/Root-Not%20Required-success?style=for-the-badge)
![License](https://img.shields.io/badge/License-GPLv3-orange?style=for-the-badge)

A complete, non-root compatibility port of Samsung Good Lock's **One Hand Operation+** (`com.samsung.android.sidegesturepad` v`9.4.23.0`) engineered to deliver the full Samsung flagship gesture experience on non-Samsung Android devices running **Android 14, 15, and 16+**.

This project replaces Samsung-exclusive One UI / `Sem*` framework calls, private system permissions, and proprietary SPR bitmap drawables with a lightweight, zero-root compatibility layer powered by standard Android Accessibility and System APIs—preserving smooth edge gestures, responsive normal edge touches, and a 100% functional Quick Tools panel.

---

## Tested Devices

Verified end-to-end across flagship phones and tablets:

| Device | Form Factor | Status |
| :--- | :--- | :--- |
| **Pixel 11 Pro XL** | Flagship Phone | Verified |
| **Xiaomi Pad 7 Pro** | Flagship Tablet | Verified |
| **iQOO Z10 Turbo** | Performance Phone | Verified |
| **Redmi Turbo 4 Pro** | Performance Phone | Verified |
| **Poco F7** | Performance Phone | Verified |

---

## Key Features & Engineering Highlights

### 1. Full Samsung Flagship Gesture Engine
- **Independent Left & Right Edge Handles** running as `TYPE_ACCESSIBILITY_OVERLAY` (`type=2032`) so handles remain responsive above apps, system UI, and full-screen views.
- **Short & Long Swipe Support**: Straight, Diagonal Up, and Diagonal Down gestures with customizable handle size, position, width, vibration feedback, and animations.
- **Navigation & System Actions**: Back, Home, Recents, Previous App, Split Screen, Notification Panel, Quick Settings, Screen Capture, Screen Lock, Power Menu, Task Switcher, Fast Action, Virtual Touch Pad, and Assistant / Circle to Search.

### 2. 100% Reliable Normal Edge Touch Pass-Through
Stock Samsung OHO+ relies on privileged `INJECT_EVENTS` to forward normal taps along the screen edges. On non-Samsung Android 14–16+ devices, normal edge taps could previously be dropped or feel intermittent. This port fixes every root cause:
- **500ms Human Tap Window**: Patches Samsung's hardcoded `200ms` (`0xc8`) tap timeout in `a6/s.smali` to `500ms` (`0x1f4`) so deliberate finger taps (typically 180ms–350ms) are never silently discarded.
- **Off-Handle Pass-Through**: Touches landing on the full-height overlay window outside active handle bounds are immediately forwarded and never consumed.
- **Android 16 Non-Zero Stroke Injection**: Ensures accessibility tap strokes carry a guaranteed 1px vector length so modern `InputDispatcher` pipelines never drop zero-length paths.
- **Clean Overlay Handoff**: Dynamically applies `FLAG_NOT_TOUCHABLE` with tuned WindowManager settle timing during pass-through dispatch and restores touchability immediately upon gesture completion.

### 3. Complete Quick Tools Panel
Every slider, media control, and toggle tile in the Quick Tools popup is mapped to standard Android APIs:

| Control / Tile | Implementation |
| :--- | :--- |
| **Brightness Slider** | `Settings.System.SCREEN_BRIGHTNESS` + `screen_brightness_float` (0–255) |
| **Auto-Brightness Toggle** | `Settings.System.putInt("screen_brightness_mode", 0/1)` |
| **Fine Volume Slider** | `AudioManager.STREAM_MUSIC` (0–150 Samsung fine-scale mapping) |
| **Media Controls** | Play/Pause, Next, Previous, Vol Up/Down via `AudioManager` + `MediaSessionManager` |
| **Wi-Fi / Bluetooth** | Direct compatibility toggles & system panel fallbacks |
| **Sound Mode** | Cycles Normal / Vibrate / Silent (with DND access) via `AudioManager` |
| **Auto-Rotate & User Rotation** | `Settings.System.ACCELEROMETER_ROTATION` & `Settings.System.USER_ROTATION` |
| **Notification Panel** | `GLOBAL_ACTION_NOTIFICATIONS` / `StatusBarManager` |
| **Screen Capture** | `GLOBAL_ACTION_TAKE_SCREENSHOT` (Android Accessibility Global Action) |
| **Screen Lock** | `GLOBAL_ACTION_LOCK_SCREEN` (preserves biometric unlock) |
| **Flashlight** | `CameraManager.setTorchMode` with live torch state tracking |
| **Night Mode (Dark Theme)** | `UiModeManager` dark mode toggle |

### 4. One UI Visual & Compatibility Layer
- **SPR Drawable Replacement**: Converts 11 proprietary Samsung `.bmp` SPR icons into crisp native Android `VectorDrawable` XMLs so all settings and panel icons render cleanly on any ROM.
- **Compat Blur Engine (`CompatBlurInfo.java`)**: Safely intercepts `SemBlurInfo` calls without crashes on non-Samsung devices.
- **Clean Action Filtering**: Automatically hides truly Samsung-exclusive hardware/firmware features (e.g., Samsung Wallet, Bixby Routines, Game Tools) while keeping all universal features active.

---

## Project Structure

```text
ONE-HAND-Operation_PLUS/
├── compat_src/
│   └── com/samsung/android/sidegesturepad/compat/
│       ├── CompatBlurInfo.java                # SemBlurInfo drop-in compatibility shim
│       ├── SGPCompatAccessibilityService.java # Accessibility overlay WM, global actions & stroke dispatch
│       └── VivoCompat.java                    # Core non-Samsung API bridge (toggles, touch pass-through, media, brightness)
├── resources/
│   └── res/xml/
│       └── sgp_accessibility_service.xml      # AccessibilityService metadata declaration
├── patch_apk.py                               # Automated smali, manifest, styles & vector drawable patcher
├── build_and_install.ps1                      # End-to-end build, DEX injection, zipalign, signing & ADB installer
├── .gitignore
├── LICENSE
└── README.md
```

---

## Quick Installation (Pre-built APK)

1. Download the latest signed APK from the **[Releases](https://github.com/smartworldarafath/ONE-HAND-Operation_PLUS/releases)** page.
2. Install the APK on your Android device.
3. Grant the required permissions (either in Android Settings or in one shot via ADB over USB):

```bash
PKG=com.samsung.android.sidegesturepad

adb shell pm grant $PKG android.permission.WRITE_SECURE_SETTINGS
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS
adb shell pm grant $PKG android.permission.BLUETOOTH_CONNECT
adb shell appops set $PKG android:get_usage_stats allow
adb shell appops set $PKG SYSTEM_ALERT_WINDOW allow
adb shell appops set $PKG WRITE_SETTINGS allow
adb shell cmd notification allow_dnd $PKG
adb shell dumpsys deviceidle whitelist +$PKG
```

4. Enable **One Hand Operation+** in **Settings → Accessibility → Downloaded / Installed Services**.
5. Open **One Hand Operation+**, toggle the master switch **On**, and customize your left/right handles!

---

## Building from Source

### Prerequisites
- **JDK 11+** (`javac`, `keytool`)
- **Python 3.9+**
- **Android SDK** (`platform-tools/adb`, `build-tools` with `d8`, `zipalign`, `apksigner`, and `platforms/android-35` or `36`)
- **Apktool** (`3.x` recommended)
- Original unmodified Samsung **One Hand Operation+ `9.4.23.0` (`arm64`, `minAPI34`)** APK

### Build Steps
1. Decode the stock Samsung APK into `apktool_out/` and keep a clean backup in `apktool_orig_bak/`:
   ```bash
   apktool d com_samsung_android_sidegesturepad_9_4_23_0_942300000_minAPI34arm64.apk -o apktool_out
   cp -r apktool_out apktool_orig_bak
   ```
2. Apply all smali, manifest, style, and vector drawable patches:
   ```bash
   python patch_apk.py
   ```
3. Compile the compatibility DEX, rebuild, zipalign, sign, and install onto your connected device:
   ```powershell
   powershell -ExecutionPolicy Bypass -File build_and_install.ps1
   ```
   *(The script automatically creates a local `debug.keystore` if none exists and never commits keystores or credentials.)*

---

## Troubleshooting

- **Accessibility Service turns off after reboot / background kill**: Lock the app in Recents and set Battery usage to **Unrestricted** (already whitelisted automatically if installed via `build_and_install.ps1`).
- **System Back gesture conflicts with edge handles**: The compatibility layer automatically adjusts edge back gesture settings when `WRITE_SECURE_SETTINGS` is granted; you can also adjust handle width/position inside the app settings.
- **Brightness or Auto-Rotate doesn't change**: Ensure **Modify system settings (`WRITE_SETTINGS`)** is allowed for One Hand Operation+.

---

## Disclaimer

This project is an independent open-source compatibility patch and runtime bridge for educational and personal interoperability purposes. **Samsung**, **One UI**, **Good Lock**, and **One Hand Operation+** are trademarks of Samsung Electronics Co., Ltd. No proprietary Samsung binaries or APKs are committed to this source tree.
