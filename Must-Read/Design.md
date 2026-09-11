# Design.md — Visual Direction for the Frontend
### SIH26184 — Predictive Cash Egress Interception
**Status: LOCKED — CyberShield Native Android App (`CyberShield/`) is the ONLY frontend.**

---

## 1. Frontend Architecture: CyberShield Native Android App
The sole user-facing client is the **CyberShield Android Application** built with **Kotlin** and **Jetpack Compose** (located in `CyberShield/`). There is no web frontend.

## 2. Core Screen Layouts (Jetpack Compose)
The Android UI comprises 3 core investigative tabs + secure auth:

1. **Auth & Security (`AuthScreen.kt`)**:
   - Domain-restricted LEA login (`@gov.in` / `@i4c.gov.in` / `@mha.gov.in`)
   - 6-digit OTP verification + brute-force lockout.
2. **Radar Screen (`RadarMapScreen.kt`)**:
   - High-contrast Dark Mode Google Map with terminal markers & cluster heatmaps.
   - Color-coded severity pins: Green (<40%), Amber (40-70%), Red (>70% Critical).
   - Bottom sheet / detail modal showing terminal type, district, and predicted egress likelihood.
3. **Investigation & XAI Screen (`InvestigationScreen.kt`)**:
   - Detailed money flow trail (Victim -> Mule L1 -> Mule L2 -> Aggregator).
   - Explainable AI breakdown cards (rule weights, points, measured triggers).
   - Human-in-the-loop decision buttons: "Approve Terminal Freeze", "Dispatch Field Patrol", "Dismiss Alert".
4. **Dispatch & Audit Screen (`DispatchScreen.kt`)**:
   - Live metrics summary strip (Active Alerts, High-Risk Mules, Intercepted Amount, Monitored Terminals).
   - Real-time dispatch action queue and chronological tamper-evident audit trail.

## 3. Official Color System
| Token | Hex | Usage |
|---|---|---|
| Deep Charcoal (Background) | `#0B0F19` | Main dark canvas |
| Card / Surface Dark | `#111827` | Containers, cards, drawers |
| Cyber Cyan | `#06B6D4` | Accent highlight, primary badges |
| I4C Blue | `#3B82F6` | Primary action buttons |
| High Risk / Critical | `#EF4444` | Severity >70%, alerts, urgent warnings |
| Medium Risk | `#F59E0B` | Severity 40-70%, warnings |
| Low / Safe | `#10B981` | Severity <40%, clean accounts |
