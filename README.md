# SIH2026 — Predictive Cash Egress Interception Platform

Real-time streaming pipeline for mule-account fraud pattern detection (fan-in, fan-out, layering, triadic cycles) and physical cash-out terminal prediction before egress occurs.

---

## 1. System Architecture & Flow

```text
Synthetic / Live Transactions
             ↓
  data-generator/producer.py (keyed by source_account_id, chronologically sorted)
             ↓
     Kafka "transactions" (3 partitions, KRaft mode)
             ↓
     pipeline/consumer.py (group_id: graph-builder-group)
             ↓
     pipeline/graph_store.py (sliding-window NetworkX graph, O(1) device index, idempotent)
             ↓
     Kafka "graph_signals" (8-field contract)
             ↓
     detection/scorer.py (modular rules: fan-in, fan-out, layering, device reuse @ threshold 0.70)
             ↓
     Kafka "risk_alerts" (with terminal coordinates: latitude, longitude)
```

---

## 2. Kafka Topics & Partitioning Strategy

| Topic | Partitions | Key Strategy | Purpose |
|---|---|---|---|
| `transactions` | **3** | `source_account_id` | Ingestion stream. Partitioning by `source_account_id` guarantees FIFO transaction ordering for every sending account. |
| `graph_signals` | **1** | Round-robin / default | Pipeline signal events emitted for counterparties after graph state updates. |
| `risk_alerts` | **1** | Round-robin / default | Flagged high-risk accounts with explainable rule evidence and predicted cash-out terminals. |

### Architectural Constraint: In-Memory Graph vs. Multi-Consumer Partitioning
* The transaction graph operates as an **in-memory NetworkX directed graph** within the pipeline consumer process.
* **Single Graph Builder Consumer:** To maintain a holistic cross-account topological graph (e.g. cross-partition fan-in to an aggregator), all 3 partitions of the `transactions` topic are consumed by a single dedicated `graph-builder-group` consumer instance.
* Horizontal scaling for production would utilize a distributed graph store (e.g., Neo4j / Apache Flink / Spark GraphX).

---

## 3. Delivery Semantics & Idempotency Invariants

* **Delivery Model:** **At-Least-Once Delivery** with **Application-Level Idempotence**.
* **Idempotency Guarantee:**
  Every transaction contains a unique `transaction_id`. When received, `GraphStore.add_transaction(tx)` checks a time-bounded deduplication set (`_seen_tx_ids`).
  $$\text{Duplicate Kafka Delivery} \implies \text{Zero mutation of graph edges, counters, device indexes, or chain depths}.$$
* **Memory Bounding:** Seen transaction IDs are automatically pruned after $2\times \text{fan\_window}$ (10 minutes), preventing memory leaks during long-running streams.

---

## 4. Poison-Pill & Error Resilience

* **Malformed JSON / Corrupted Bytes:** Unparseable payloads are intercepted by `_deserialize_transaction()` and logged as warnings; the consumer skips the poison pill without crashing.
* **Missing Fields:** Transactions missing required fields are rejected by `process_transaction()` before mutating the graph.
* **Graceful Shutdown:** `SIGINT` and `SIGTERM` signals break the poll loop cleanly, flush buffered producer messages, and commit consumer offsets before exiting.

---

## 5. Quick Start & Execution

### A. Start Kafka Broker
```bash
docker compose up -d
```

### B. Run Complete Test Suite
```bash
.venv/bin/pytest tests/ -v
```

### C. Run Full 1,000-Transaction Live Streaming Replay
```bash
# Terminal 1: Start Pipeline Consumer
.venv/bin/python pipeline/consumer.py

# Terminal 2: Start Detection Scorer
.venv/bin/python detection/scorer.py

# Terminal 3: Stream Transactions to Kafka
.venv/bin/python data-generator/producer.py
```

---

## 6. Verified Detection Baseline (1,000 Synthetic Transactions)

* **Legitimate Traffic:** 973 transactions across 200 accounts.
* **Fraud Injections:** 27 transactions across 7 attack campaigns (`SC001`–`SC007`: fan-in, fan-out, layering, triadic).
* **Scenario-Level Interception:** **7 / 7 (100.0%)**
* **Precision:** **81.82%**
* **Recall:** **66.67%** (catches all accumulation/dispersion hops after minimum threshold build-up)
* **F1-Score:** **73.47%**
* **Legitimate Alert Rate:** **0.41%** (4 false alerts across 973 normal transactions)
