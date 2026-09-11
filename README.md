# Predictive Cash Egress Interception Platform (SIH26184)
### Ministry of Home Affairs / I4C Cybercrime Interception & Defense System

> **A real-time cyber fraud interception system that detects mule account networks and proactively predicts physical cash-out locations (ATMs / AEPS micro-ATMs) before illicit cash egress occurs.**

---

## 1. System Architecture & Data Flow

```text
Synthetic / Live Transactions
             ↓
  data-generator/producer.py (keyed by source_account_id, chronologically sorted)
             ↓
     Kafka "transactions" (3 partitions, KRaft single-broker)
             ↓
     pipeline/consumer.py (group_id: graph-builder-group)
             ↓
     pipeline/graph_store.py (sliding-window NetworkX graph, O(1) device index, idempotent)
             ↓
     Kafka "graph_signals" (8-field contract)
             ↓
     detection/scorer.py (8 modular rules @ score >= 60 -> HIGH/CRITICAL)
             ↓
     detection/terminal_ranking.py (spatial proximity + historical affinity ranking)
             ↓
     Kafka "risk_alerts" (with terminal coordinates: latitude, longitude)
             ↓
    ┌─────────────────────────────────────────────────────────────┐
    │                                                             │
    ▼                                                             ▼
Notification Subsystem (Sprint 4)                   FastAPI Backend API (`api/server.py`)
(SMS & Email to Bank/Security/Investigation)        (LAN Sync on 0.0.0.0:8080)
    │                                                             │
    └─────────────────────────────┬───────────────────────────────┘
                                  ▼
                CyberShield Native Android Kotlin App
                (Jetpack Compose · MapLibre OSM · Live Sync)
                **SOLE USER-FACING FRONTEND** (No Web App)
```

---

## 2. Platform Subsystems

### 1. Data Generation (Workstream 1)
* **Modular Generator (`data-generator/`):** Generates realistic normal traffic + injected fraud patterns (fan-in, fan-out, layering chains, triadic cycles) with power-law amount distributions across 16 fraud archetypes.
* **Producer (`data-generator/producer.py`):** Normalizes transactions to the 7 locked Kafka fields, keys messages by `source_account_id`, and replays streams in true chronological order.

### 2. Kafka Streaming & Graph Pipeline (Workstream 2)
* **Kafka Topics:** `transactions` (3 partitions), `graph_signals` (1 partition), `risk_alerts` (1 partition).
* **GraphStore (`pipeline/graph_store.py`):** In-memory directed graph (NetworkX) with sliding-window edge eviction, thread-safe deduplication (`_seen_tx_ids`), and structural topology queries.
* **Poison-Pill Handling:** Corrupted non-JSON bytes and malformed events are safely skipped without bringing down the consumer.

### 3. Detection Engine & Terminal Ranking (Workstream 3)
* **8 Heuristic Rules (`detection/rules/`):**
  1. `fan_in_rule`: Rapid accumulation across multiple senders.
  2. `fan_out_rule`: Rapid dispersion to multiple targets.
  3. `velocity_rule`: Swift pass-through latency (inbound-to-outbound gap).
  4. `layering_rule`: Deep multi-hop chain traversal.
  5. `amount_movement_rule`: High forwarded-fund proportion.
  6. `account_age_rule`: Freshly created mule accounts.
  7. `device_fingerprint_rule`: Shared hardware fingerprint clusters.
  8. `terminal_affinity_rule`: Prior cash-out location match.
* **Terminal Priority Ranking (`detection/terminal_ranking.py`):** Ranks candidate physical egress terminals by spatial distance, historical affinity, and terminal type.
* **Alert Dispatcher (`detection/alert_dispatcher.py`):** Publishes `risk_alerts` with explainable evidence trails and predicted withdrawal time windows.

### 4. SMS & Email Notification Subsystem (Sprint 4)
* **Modular Notification Engine (`pipeline/notification_service.py`):** Dispatches channel-specific alerts (concise SMS and structured investigation emails with HTML + plain text) across key case milestones without blocking transaction processing.
* **Supported Events:**
  - `HIGH_RISK_CASE`: Initial detection and predicted terminal assignment.
  - `CONFIRMED_FRAUD`: Payer confirms unauthorized transfer via interactive verification.
  - `CASHOUT_ATTEMPT_DETECTED`: Physical or cardless withdrawal attempted at ATM.
  - `WITHDRAWAL_BLOCKED`: Hard ATM/digital block intercepts cash egress.
  - `CASE_ESCALATED`: Priority escalated to CRITICAL.
  - `POLICE_ALERT_SENT`: LEA investigation package dispatched to field patrol.
  - `PENDING_CONFIRMATION`: High-risk transfer placed on digital hold awaiting verification.
* **Provider Architecture:**
  - Default: Safe mock providers labeled `[SIMULATED]` (`MockSmsProvider`, `MockEmailProvider`).
  - Production Gateways: Pluggable HTTP/REST SMS (`RealSmsProvider`) and standard SMTP/TLS (`SmtpEmailProvider`) configurable via environment variables without hardcoded credentials.
* **Reliability & Idempotency:** Deterministic hashing keys prevent duplicate notifications; bounded retry mechanism (up to 3 retries) handles transient failures gracefully without crashing.
* **Persistence:** All notifications stored in SQLite (`cybershield.db -> notifications` table).

### 5. Frontend & Backend Presentation Layer
* **CyberShield Native Android App (`CyberShield/`):** **The sole frontend for this project.** Native Kotlin + Jetpack Compose application featuring:
  - Cases Queue with plain-language summaries and filtering.
  - Case Detail Screen with XAI evidence, money trail diagrams, action decisions ("Send to Police", "Freeze Account", "Dismiss"), and authoritative `NotificationDeliveryCard` delivery status.
  - Interactive Radar Map (MapLibre OSM) with spatial clustering and terminal markers.
  - Activity screen displaying tamper-evident audit ledger entries.
* **FastAPI Backend Service (`api/server.py`):** Lightweight JSON REST API running on `0.0.0.0:8080` for local LAN access by Android physical devices and emulators:
  - `GET /cases`: Retrieve active cases with investigation state.
  - `GET /cases/{case_id}/notifications`: Retrieve authoritative notification delivery items.
  - `POST /cases/{case_id}/notify`: Trigger manual or programmatic notifications.
  - `POST /cases/{case_id}/act`: Execute investigator decisions (freeze, approve, escalate).

> **FRONTEND ARCHITECTURE MANDATE:**
> There is **NO** web frontend, HTML dashboard, or JavaScript framework. The CyberShield Native Android Kotlin App is the exclusive presentation client.

---

## 3. Quick Start & Execution

### A. Environment Setup & Tests
```bash
# Install dependencies
pip install -r requirements.txt

# Run complete test suite (127+ unit, notification, schema, rule, and integration tests)
pytest tests/ -v
```

### B. Run Sprint 4 Notification Demo
```bash
# Run operational end-to-end notification lifecycle demo
python -m scripts.demo_notification_system
```

### C. Start Backend API Server for CyberShield Android
```bash
# Start FastAPI backend (LAN accessible on port 8080)
python -m uvicorn api.server:app --host 0.0.0.0 --port 8080
```

### D. Run Full Live Streaming Pipeline
```bash
# 1. Start Kafka Broker
docker compose up -d

# 2. Start Pipeline Consumer (Terminal 1)
python pipeline/consumer.py

# 3. Start Detection Scorer (Terminal 2)
python detection/scorer.py

# 4. Publish Live Transactions Stream (Terminal 3)
python data-generator/producer.py
```

### E. Build CyberShield Android App
```bash
cd CyberShield
./gradlew assembleDebug
# APK generated at: CyberShield/app/build/outputs/apk/debug/app-debug.apk
```
