# Cyber Shield: Predictive Cashout Radar

### SIH26184 — Ministry of Home Affairs / I4C Cybercrime Defense System

A production-grade native Android application built with **Kotlin** and **Jetpack Compose** for real-time cybercrime cashout prediction, investigation, and dispatch management.

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

## Screens

| # | Screen | Purpose |
|---|--------|---------|
| 0 | **Auth** | Domain-restricted login (`@police.gov.in`, `@gov.in`, `@rbi.org.in`), 6-digit OTP, 48-hour lockdown after 5 failures |
| 1 | **Cashout Radar** | Interactive GIS map centered on Sector 18 Noida with risk heatmaps and color-coded terminal markers |
| 2 | **Investigation** | XAI score breakdown (velocity, topology, device, spatial), money trail visualization, dispatch/hold/dismiss actions |
| 3 | **Dispatch Center** | Summary KPIs, pending review queue, chronological audit log with timeline |

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

## Build

1. Open in Android Studio Hedgehog (2023.1.1) or later
2. Add your Google Maps API key to `AndroidManifest.xml` (replace `MAPS_API_KEY_PLACEHOLDER`)
3. Sync Gradle and run on a device or emulator (API 26+)

## Demo OTP

Use `123456` as the OTP for any authorized domain email address.

## Key Features

- **Zero-backend demo**: All data is served from `MockDataRepository` — fully offline presentable
- **Brute-force protection**: 5 failed OTP attempts trigger a visible 48-hour lockdown with countdown
- **XAI explainability**: Each risk signal shows its exact contribution percentage and rationale
- **Audit trail**: Every action (approve, hold, dismiss) is recorded in the chronological audit log
- **Human-in-the-loop**: All critical decisions require explicit officer confirmation via dialogs

---

*Built for Smart India Hackathon 2026 — Problem Statement SIH26184*
