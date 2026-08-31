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
   ┌──────────────────────────────────────────────┐
   │                                              │
   ▼                                              ▼
CyberShield Native Android App        FastAPI Web Dashboard
(MapLibre OSM + Jetpack Compose)     (Leaflet.js + Evidence Panel)
```

---

## 2. Platform Subsystems

### 1. Data Generation (Workstream 1)
* **Modular Generator (`data-generator/`):** Generates realistic normal traffic + injected fraud patterns (fan-in, fan-out, layering chains, triadic cycles) with power-law amount distributions.
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

### 4. Presentation & Visualization Layer
* **CyberShield Android App (`CyberShield/`):** Native Android Kotlin application (Jetpack Compose, MapLibre OSM map, Investigation XAI money trails, Dispatch & Audit timelines, domain-restricted LEA authentication).
* **FastAPI Web Dashboard (`detection/dashboard/`):** Lightweight web dashboard serving alert feeds, Leaflet.js interactive maps, and evidence panels.

---

## 3. Quick Start & Execution

### A. Environment Setup & Tests
```bash
# Install dependencies
pip install -r requirements.txt

# Run complete test suite (24 unit, schema, rule, and integration tests)
pytest tests/ -v
```

### B. Generate Synthetic Data
```bash
python data-generator/generate.py
```

### C. Run Full Live Streaming Pipeline
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

### D. Run Web Dashboard
```bash
python detection/dashboard/app.py
# Open http://localhost:8000 in your browser
```

### E. Build CyberShield Android App
```bash
cd CyberShield
./gradlew assembleDebug
# APK generated at: CyberShield/app/build/outputs/apk/debug/app-debug.apk
```
