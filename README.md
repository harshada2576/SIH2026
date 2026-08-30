# Predictive Cash Egress Interception (SIH26184)
### Ministry of Home Affairs / I4C Cybercrime Interception & Defense System

> **A real-time cyber fraud interception system that detects mule account networks and proactively predicts physical cash-out locations (ATMs / AEPS micro-ATMs) before illicit cash egress occurs.**

---

## 🏗️ Architecture Overview

The system consists of two primary layers:
1. **Detection & Pipeline Backend (Python 3.11+)**:
   - Synthetic data generation with AMLSim-style power-law distributions and injected fraud patterns (fan-in, fan-out, layering chains, device sharing).
   - Ingestion and real-time directed transaction graph updates via in-memory `GraphStore` (NetworkX).
   - Explainable heuristic scoring engine (8 independent rules: velocity, fan-in, fan-out, layering depth, amount movement, account age, device fingerprint, terminal affinity).
   - Terminal priority ranking and predictive time-window estimation.
   - Alert dispatching for Law Enforcement Agencies (LEA).
2. **CyberShield Native Android App (Frontend - Kotlin & Jetpack Compose)**:
   - **MANDATE**: CyberShield (`CyberShield/`) is the **ONLY** frontend for this project. There are NO web or HTML dashboards.
   - **Radar Map (`RadarMapScreen.kt`)**: Real-time Google Maps interface with risk-coded terminal markers and candidate heatmap overlays.
   - **Investigation & XAI (`InvestigationScreen.kt`)**: Money trail visualization (Victim → Mule L1 → Mule L2 → Aggregator) + rule score breakdowns + human-in-the-loop freeze/dispatch actions.
   - **Dispatch & Audit (`DispatchScreen.kt`)**: Interception metrics summary and tamper-evident audit timeline.
   - **LEA Auth (`AuthScreen.kt`)**: Domain-restricted login (`@gov.in`, `@i4c.gov.in`, `@mha.gov.in`) with OTP verification.

---

## 🚀 Running & Testing

### 1. Python Backend Testing
```bash
# Install shared requirements
pip install -r requirements.txt

# Run full backend test suite (24 unit and integration tests)
python -m pytest
```

### 2. CyberShield Android Frontend
The native Android app resides in the `CyberShield/` directory.

```powershell
# Navigate to Android project directory
cd CyberShield

# Run unit tests
.\gradlew.bat testDebugUnitTest

# Build Debug APK
.\gradlew.bat assembleDebug

# Install and run on connected Android emulator/device
.\gradlew.bat installDebug
```

Output APK will be located at:
`CyberShield/app/build/outputs/apk/debug/app-debug.apk`

---

## 📁 Repository Structure

```
SIH2026/
├── Must-Read/                         # Core system architecture, rules & PRD
│   ├── Architecture.md
│   ├── PRD.md
│   ├── Rules.md
│   ├── Phases.md
│   ├── Design.md
│   └── Memory.md
│
├── CyberShield/                       # SOLE FRONTEND: Native Android Kotlin App
│   ├── app/src/main/java/com/i4c/cybershield/
│   │   ├── MainActivity.kt
│   │   ├── MainViewModel.kt
│   │   ├── model/Models.kt
│   │   ├── data/MockDataRepository.kt
│   │   └── ui/
│   │       ├── auth/AuthScreen.kt
│   │       ├── radar/RadarMapScreen.kt
│   │       ├── investigation/InvestigationScreen.kt
│   │       └── dispatch/DispatchScreen.kt
│   └── build.gradle.kts
│
├── shared/
│   ├── schemas.py                     # The 4 JSON schemas (shared contract)
│   ├── kafka_utils.py
│   └── terminals.json                 # Static reference ATM/AEPS nodes
│
├── pipeline/
│   └── graph_store.py                 # NetworkX in-memory account graph
│
├── detection/
│   ├── scorer.py                      # Heuristic scoring engine (0-100)
│   ├── terminal_ranking.py            # Terminal egress priority algorithm
│   ├── alert_dispatcher.py            # Alert formatter & logger
│   └── rules/                         # 8 independently-testable rules
│
└── tests/
    ├── test_schemas.py
    ├── test_rules.py
    └── test_integration.py
```
