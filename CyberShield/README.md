# Cyber Shield: Predictive Cashout Radar

### SIH26184 — Ministry of Home Affairs / I4C Cybercrime Defense System

A production-grade native Android application built with **Kotlin** and **Jetpack Compose** for real-time cybercrime cashout prediction, investigation, and dispatch management.

---

## Table of Contents
- [Prerequisites](#prerequisites)
- [Project Structure](#architecture)
- [Build the Project (from source)](#build-the-project)
- [Run on an Emulator](#run-on-an-emulator)
- [Run on a Physical Device](#run-on-a-physical-device)
- [Install & Verify the APK via ADB](#install--verify-the-apk-via-adb)
- [Demo OTP & Testing Guide](#demo-otp--testing-guide)
- [Google Maps API Key (required for Radar tab)](#google-maps-api-key)
- [Color System](#color-system)
- [Key Features](#key-features)

---

## Prerequisites

| Tool | Version tested | Notes |
|------|----------------|-------|
| JDK | 17 (LTS) | e.g. Microsoft OpenJDK 17. Must be **17** (AGP 8.4 requires it) |
| Android SDK | platform 34, build-tools 34.0.0 | cmdline-tools + platform-tools (adb) required |
| Gradle | 8.6 (wrapper included) | Use `gradlew.bat` on Windows |
| Emulator / device | API 26+ (target 34) | AVD `x86_64` image recommended |

Set environment variables (Windows PowerShell):

```powershell
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT = "$env:LOCALAPPDATA\Android\Sdk"
```

The project already contains a `local.properties` pointing to the SDK:

```
# local.properties
sdk.dir=C:/Users/Admin/AppData/Local/Android/Sdk   # use FORWARD slashes
```

> **Important:** In `local.properties`, paths must use **forward slashes** (`C:/...`), not backslashes. Backslashes are Java-properties escape characters and will break the build with `IOException: The filename, directory name, or volume label syntax is incorrect`.

---

## Architecture

```
com.i4c.cybershield/
├── MainActivity.kt                  # Entry point
├── MainViewModel.kt                 # Single source of truth (auth, nav, actions, audit)
├── data/
│   └── MockDataRepository.kt        # Offline mock data for all screens
├── model/
│   └── Models.kt                    # Domain models (Terminal, Complaint, Trail, XAI, Audit)
└── ui/
    ├── theme/
    │   ├── Color.kt                 # Official I4C color palette (7 primary + derived)
    │   └── Theme.kt                 # Material3 dark theme + typography
    ├── auth/
    │   └── AuthScreen.kt            # Domain-restricted login, OTP, brute-force lockdown
    ├── radar/
    │   └── RadarMapScreen.kt        # Live Google Maps + heatmap overlays + terminal markers
    ├── investigation/
    │   └── InvestigationScreen.kt   # XAI breakdown, money trail, human-in-the-loop decisions
    ├── dispatch/
    │   └── DispatchScreen.kt        # Summary metrics, pending queue, audit timeline
    ├── navigation/
    │   └── NavGraph.kt              # Auth ↔ Main navigation
    └── screens/
        └── MainScreen.kt            # 3-Tab Scaffold + custom bottom navigation
```

---

## Build the Project

From the project root (`CyberShield\`):

```powershell
# 1. Clean (optional but recommended after changing SDK/Gradle)
.\gradlew.bat clean

# 2. Build the debug APK
.\gradlew.bat assembleDebug

# 3. (Optional) install to the emulator/device directly
.\gradlew.bat installDebug
```

Output APK:

```
app\build\outputs\apk\debug\app-debug.apk
```

> If `gradlew.bat` is missing, generate the wrapper from an installed Gradle 8.6:
> ```powershell
> gradle wrapper --gradle-version 8.6
> ```

---

## Run on an Emulator

### 1. Create an AVD (first time only)

```powershell
# List available AVDs
& "$env:ANDROID_HOME\cmdline-tools\latest\bin\avdmanager.bat" list avd

# Create a new AVD (example: pixel_7, Android 34, x86_64)
echo no | & "$env:ANDROID_HOME\cmdline-tools\latest\bin\avdmanager.bat" create avd `
    -n CyberShield_AVD -k "system-images;android-34;google_apis;x86_64" -d "pixel_7"
```

> Make sure the system image is installed first:
> ```powershell
> echo y | & "$env:ANDROID_HOME\cmdline-tools\latest\bin\sdkmanager.bat" "system-images;android-34;google_apis;x86_64" "emulator"
> ```

### 2. Launch the emulator

On machines with GPU/driver conflicts the emulator can crash with the default `auto` GPU mode (render threads exit with `Error reading from client fd`). Use **`-gpu swiftshader_indirect`** for reliable software rendering.

> **Stability tip:** On low-RAM / no-GPU hosts, software rendering (swiftshader) is slow and the running copy can throw persistent **system** ANR dialog boxes that steal input focus. Reduce the screen resolution, raise the RAM, and skip snapshots to keep it responsive:

```powershell
# Stable, tested launch (720x1280, 3 GB RAM, software GPU, no boot animation/snapshot):
& "$env:ANDROID_HOME\emulator\emulator.exe" -avd CyberShield_AVD `
    -gpu swiftshader_indirect -memory 3072 `
    -skin 720x1280 -no-snapshot -no-boot-anim
```

After it boots, **disable animations** to cut system load and avoid the system ANR dialogs that otherwise steal input focus during interactive tests:

```powershell
$adb = "$env:ANDROID_HOME\platform-tools\adb.exe"
& $adb shell settings put global window_animation_scale 0
& $adb shell settings put global transition_animation_scale 0
& $adb shell settings put global animator_duration_scale 0
```


### 3. Wait for boot & install

```powershell
# Confirm the device is seen
& "$env:ANDROID_HOME\platform-tools\adb.exe" devices

# Wait until fully booted (returns "1")
& "$env:ANDROID_HOME\platform-tools\adb.exe" shell getprop sys.boot_completed

# Install the built APK
& "$env:ANDROID_HOME\platform-tools\adb.exe" install -r app\build\outputs\apk\debug\app-debug.apk

# Launch the app
& "$env:ANDROID_HOME\platform-tools\adb.exe" shell am start -n com.i4c.cybershield/.MainActivity
```

---

## Run on a Physical Device

1. Enable **Developer options** on the phone (tap Build number 7× in Settings → About phone).
2. Enable **USB debugging**.
3. Plug the phone in and accept the RSA prompt.
4. Verify with `adb devices` (device shows as `device`, not `unauthorized`).
5. Build & install:
   ```powershell
   .\gradlew.bat installDebug
   ```

---

## Install & Verify the APK via ADB

```powershell
$adb = "$env:ANDROID_HOME\platform-tools\adb.exe"

# Install over an existing copy
& $adb install -r app\build\outputs\apk\debug\app-debug.apk

# Confirm the app is in the foreground (resumed)
& $adb shell dumpsys activity activities | findstr "topResumedActivity"

# Confirm the app's process is healthy (no FATAL/crash in its recent log)
& $adb exec-out logcat -d -v brief | findstr /i "cybershield" | findstr /v "ActivityManager"

# Capture a screenshot of the current screen
& $adb exec-out screencap -p > screen.png

# Force-stop the app
& $adb shell am force-stop com.i4c.cybershield
```

---

## Demo OTP & Testing Guide

**Demo OTP: `123456`** (for any authorized domain email address).

### Login steps
1. Open the app → **Auth screen**.
2. Enter an **official email** ending in one of:
   - `@police.gov.in`
   - `@gov.in`
   - `@rbi.org.in`
   - e.g. `officer@police.gov.in`
3. Tap **SEND SECURE OTP** → an info card shows `Demo OTP: 123456`.
4. Enter **`123456`**.
5. Tap **VERIFY & LOGIN** → you land on the main **3-tab** screen.

### Testing the 3 tabs (after login)

| Tab | What to verify |
|-----|----------------|
| **Cashout Radar** | Bottom-nav first tab. Shows Google Map with terminal markers. *(Needs a valid Maps API key — see below; otherwise the map area is blank/grey.)* |
| **Investigation** | Tap **Approve** / **Bank Hold** / **Dismiss** → confirmation dialogs appear; confirm → audit log updates. |
| **Dispatch Center** | Shows summary KPIs, pending review queue, chronological audit timeline (grows as actions are taken). |

### Brute-force lockdown (security)
5 consecutive wrong OTP attempts → visible **48-hour lockdown** screen with a live countdown.

### Automated UI testing via ADB (no touchscreen needed)

You can drive the whole flow from the shell. Tap coordinates are **resolution-dependent**, so first confirm the emulator's screen size and look up exact button bounds.

```powershell
$adb = "$env:ANDROID_HOME\platform-tools\adb.exe"

# 1. Confirm the screen size (matches the -skin you launched with, e.g. 720x1280)
& $adb shell wm size

# 2. Dump the on-screen element bounds (works on dialogs / native views):
& $adb exec-out uiautomator dump /dev/tty > ui.xml
```

The Auth screen is a vertically-centered column. On a **720×1280** AVD the email field sits around `(360, 920)`, and the flow is:

```powershell
# Focus the email field, then type an authorized email
& $adb shell input tap 360 920
& $adb shell input text "officer@police.gov.in"

# Close the keyboard
& $adb shell input keyevent 4

# Tap "SEND SECURE OTP" (~52% down the screen), then type the demo OTP
& $adb shell input tap 360 1104
& $adb shell input text "123456"

# Close the keyboard, then tap "VERIFY & LOGIN"
& $adb shell input keyevent 4
& $adb shell input tap 360 1220

# Switch tabs via the bottom navigation bar (3 tabs, evenly spaced) e.g. Investigation (2nd of 3):
& $adb shell input tap 360 1240
```

> On a slow software-rendered emulator `adb shell input ...` can take a while to return — allow up to ~90 s and retry if it times out. For exact button positions, dump the hierarchy with `uiautomator` (or read `screencap`) instead of relying on the estimates above.

---

## Google Maps API Key

The manifest currently contains a placeholder:

```xml
<!-- app/src/main/AndroidManifest.xml -->
<meta-data
    android:name="com.google.android.geo.API_KEY"
    android:value="MAPS_API_KEY_PLACEHOLDER" />
```

To make the **Radar (map) tab** display, replace `MAPS_API_KEY_PLACEHOLDER` with a valid **Google Maps Android API key**:

1. Create a key in the [Google Cloud Console](https://console.cloud.google.com) (Maps SDK for Android).
2. Restrict it to your app's **package name** (`com.i4c.cybershield`) and **SHA-1 signing certificate**.
3. Paste it into `AndroidManifest.xml`.

**Without a valid key:** the app builds and runs, and the Auth / Investigation / Dispatch tabs all work — but the map in the Cashout Radar tab shows blank/grey.

> The debug keystore fingerprint (used for local debug builds) is at `%USERPROFILE%\.android\debug.keystore`. Get it with:
> ```powershell
> & "$env:ANDROID_HOME\build-tools\34.0.0\keytool" -list -v -alias androiddebugkey `
>     -keystore "$env:USERPROFILE\.android\debug.keystore" -storepass android
> ```

---

## Screens

| # | Screen | Purpose |
|---|--------|---------|
| 0 | **Auth** | Domain-restricted login (`@police.gov.in`, `@gov.in`, `@rbi.org.in`), 6-digit OTP, 48-hour lockdown after 5 failures |
| 1 | **Cashout Radar** | Interactive GIS map centered on Sector 18 Noida with risk heatmaps and color-coded terminal markers |
| 2 | **Investigation** | XAI score breakdown (velocity, topology, device, spatial), money trail visualization, dispatch/hold/dismiss actions |
| 3 | **Dispatch Center** | Summary KPIs, pending review queue, chronological audit log with timeline |

---

## Color System

| Token | Hex | Usage |
|-------|-----|-------|
| `BgDeepSlate` | `#252422` | Main background, TopBar, Bottom Nav |
| `SurfaceCharcoal` | `#403D39` | Card fills, dialogs, text fields |
| `BorderTaupe` | `#CCC5B9` | Borders, muted text, inactive indicators |
| `TextOffWhite` | `#FFFCF2` | Primary headers, main text |
| `AlertOrange` | `#EB5E28` | Action buttons, critical risk badges |
| `SuccessGreen` | `#38B000` | Live status, approved actions |
| `MediumCyan` | `#00E5FF` | Medium risk indicators |

---

## Key Features

- **Zero-backend demo**: All data is served from `MockDataRepository` — fully offline presentable
- **Brute-force protection**: 5 failed OTP attempts trigger a visible 48-hour lockdown with countdown
- **XAI explainability**: Each risk signal shows its exact contribution percentage and rationale
- **Audit trail**: Every action (approve, hold, dismiss) is recorded in the chronological audit log
- **Human-in-the-loop**: All critical decisions require explicit officer confirmation via dialogs

---

*Built for Smart India Hackathon 2026 — Problem Statement SIH26184*
