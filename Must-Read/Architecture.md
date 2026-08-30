# Architecture.md — System Architecture & Interface Contract
### SIH26184 — Predictive Cash Egress Interception
**Status: LOCKED (schemas + topics). Anyone changing anything below must post it in the group chat before building against it.**

---

## 0. How to use this document
This is the single most important file on the team. All 6 of you are prompting AI tools (Claude, ChatGPT, Copilot, etc.) independently, in parallel, for 3 days. AI tools don't know what your teammates' AI sessions are building. **This file is the shared brain that keeps 3 independently-built pieces compatible.**

Before you open any coding session:
1. Paste the relevant workstream section of this file into your AI chat as the first message.
2. Tell your AI tool: "Do not deviate from these JSON schemas, topic names, or folder paths without me confirming."
3. If your AI suggests a different library, a different schema field, a different folder layout — that's a **stop and ask the group** moment, not a "sure, why not."

---

## 1. Problem framing (one paragraph, so every AI session starts oriented the same way)
We're building a prototype that ingests a stream of financial transactions, detects mule-account fraud patterns (fan-in, fan-out, layering) using an explainable heuristic engine running over a graph representation of accounts and transactions, and predicts + alerts on the likely physical cash-out terminal (ATM/AEPS micro-ATM) before withdrawal happens. The pipeline is built on Kafka to demonstrate that the architecture scales to real transaction volumes, even though the actual demo dataset stays small (thousands, not millions, of records).

---

## 2. High-level system diagram

```
                         ┌───────────────────────────┐
                         │   WORKSTREAM 1             │
                         │   Synthetic Data Generator  │
                         │   (patterns.py, generate.py)│
                         └──────────────┬──────────────┘
                                        │ publishes JSON
                                        │ (Transaction Event schema)
                                        ▼
                         ┌───────────────────────────┐
                         │        KAFKA BROKER          │
                         │  topic: "transactions"       │
                         │  partitions: keyed by         │
                         │  district_pincode / hash(src) │
                         └──────────────┬──────────────┘
                                        │ consumed by
                                        ▼
                         ┌───────────────────────────┐
                         │   WORKSTREAM 2              │
                         │   Kafka Consumer +           │
                         │   Graph Builder (networkx)   │
                         │   (consumer.py, graph_store.py)│
                         └──────────────┬──────────────┘
                                        │ exposes graph state
                                        │ via in-process call or
                                        │ topic: "graph_updates" (optional)
                                        ▼
                         ┌───────────────────────────┐
                         │   WORKSTREAM 3               │
                         │   Detection Engine           │
                         │   (scorer.py — heuristic       │
                         │   rules, NOT a trained model) │
                         └──────────────┬──────────────┘
                                        │ publishes JSON
                                        │ (Risk Alert schema)
                                        ▼
                            ┌───────────┴────────────┐
                            ▼                          ▼
                 ┌────────────────────┐    ┌────────────────────────┐
                 │ Alert Dispatcher     │    │ CyberShield Android App│
                 │ (console/webhook/    │    │ (Kotlin + Jetpack      │
                 │  email stub)          │    │  Compose Radar Map)    │
                 └────────────────────┘    └────────────────────────┘
```

### Why this shape, specifically
- **Kafka sits between every stage**, not just at ingestion. This is deliberate — it's what lets you show a judge "this isn't a script that runs top-to-bottom once, it's a pipeline where each stage can scale independently by adding consumers." That's the actual scalability argument, and it's cheap to build because Kafka does the hard part.
- **The graph store is in-memory (`networkx`)**, not a graph database. For a 3-day prototype with a dataset in the thousands-of-nodes range, a real graph DB (Neo4j) buys you nothing except setup risk. You *talk about* Neo4j/Spark GraphX as the production-scale answer in your architecture slide, but you don't build it.
- **Detection is a rules engine, not a trained model.** This is a deliberate, defensible choice (see PRD.md "explicitly out of scope") — a heuristic scorer is fully explainable, fast to build, and directly demonstrates the detection *logic* a judge cares about without the multi-week risk of training a GNN.

---

## 3. Sequence diagram — one transaction's journey (for your demo narration)

```
Data Generator          Kafka             Consumer/Graph        Detection        CyberShield Android
     |                    |                     |                   |                 |
     |--publish txn------>|                     |                   |                 |
     |                    |--deliver----------->|                   |                 |
     |                    |                     |--update graph     |                 |
     |                    |                     |  (add edge,        |                 |
     |                    |                     |   recompute        |                 |
     |                    |                     |   fan-in count)    |                 |
     |                    |                     |--notify/poll------>|                 |
     |                    |                     |                   |--run rules on   |
     |                    |                     |                   |  graph neighborhood
     |                    |                     |                   |--threshold      |
     |                    |                     |                   |  crossed?       |
     |                    |                     |                   |--publish alert->|
     |                    |                     |                   |                 |--render on radar map
     |                    |                     |                   |                 |--show XAI evidence & trail
```

Use this exact diagram (or redraw it) as a slide — it's your "here's how data actually flows through our system" visual, and it maps 1:1 onto the demo you're going to click through live.

---

## 4. Tech stack (locked)

| Layer | Choice | Why | Explicitly avoid |
|---|---|---|---|
| Language | Python 3.11+ (Backend) & Kotlin (Android) | High developer velocity for pipeline & production native mobile defense client | Node, Go, web-only wrappers |
| Streaming | Kafka (local, single-broker, Docker) | Industry-standard, judges will recognize the name, genuinely does demonstrate the scaling pattern | Multi-broker cluster, cloud-managed Kafka (MSK/Confluent Cloud) — setup risk not worth it this week |
| Kafka client | `kafka-python` or `confluent-kafka` (pick one, both pairs use the same one) | Stable, well-documented | Mixing both across workstreams |
| Graph store | `networkx` (in-memory) | Zero setup, good enough for thousands of nodes, has built-in centrality/motif functions you can cite | Neo4j, Spark GraphX (mention only, don't install) |
| Frontend Dashboard (ONLY 1) | **CyberShield Native Android App (`CyberShield/`)** | Kotlin, Jetpack Compose, Material3, Google Maps SDK, Live Heatmaps & Dispatch Queue | Web frontend, HTML, Leaflet.js, React (No web frontend needed) |
| Data format | JSON everywhere | Human-readable, fastest for 3 pairs to debug against each other | Avro/Protobuf (adds schema-registry complexity you don't need this week) |
| Containerization | Docker + `docker-compose.yml` for Kafka + Zookeeper (or KRaft mode, no Zookeeper) | One command (`docker compose up`) to get Kafka running on any teammate's laptop | Manual Kafka binary install (version mismatches waste hours) |

---

## 5. Folder / project structure (create this exact skeleton on day 1)

```
SIH2026/
│
├── README.md                     # one-page: what this is, how to run it end-to-end
├── docker-compose.yml            # Kafka + Zookeeper (or KRaft), single broker
├── requirements.txt              # shared Python deps (or per-folder requirements.txt)
├── .env.example                  # KAFKA_BOOTSTRAP_SERVERS=localhost:9092 etc.
│
├── Must-Read/                         # this file + PRD/Rules/Phases/Design/Memory
│   ├── Architecture.md
│   ├── PRD.md
│   ├── Rules.md
│   ├── Phases.md
│   ├── Design.md
│   └── Memory.md
│
├── shared/
│   ├── schemas.py                # THE 4 schemas below, as dataclasses or pydantic models
│   │                              # — import this in all 3 workstreams, don't redefine locally
│   └── kafka_utils.py            # shared producer/consumer boilerplate (topic names, config)
│
├── data-generator/                # WORKSTREAM 1
│   ├── generate.py                # entrypoint — generates N transactions
│   ├── patterns.py                # fan-in / fan-out / layering / triadic injection logic
│   ├── normal_traffic.py          # baseline "boring" transaction generator
│   ├── producer.py                # publishes generated events to Kafka topic "transactions"
│   ├── config.py                  # tunable params: N accounts, % fraudulent, event rate/sec
│   └── requirements.txt
│
├── pipeline/                      # WORKSTREAM 2
│   ├── consumer.py                # reads "transactions", feeds graph_store
│   ├── graph_store.py             # networkx wrapper: add_transaction(), get_neighborhood(), fan_in_count()
│   ├── partition_strategy.py      # how keys map to partitions (district_pincode / hash)
│   └── requirements.txt
│
├── detection/                     # WORKSTREAM 3
│   ├── scorer.py                  # heuristic rules — reads graph_store, computes risk_score
│   ├── rules/                     # one file per rule, so rules are independently testable
│   │   ├── fan_in_rule.py
│   │   ├── velocity_rule.py
│   │   ├── device_fingerprint_rule.py
│   │   └── terminal_affinity_rule.py
│   ├── alert_dispatcher.py        # publishes to "risk_alerts" topic + console/webhook stub
│   ├── dashboard/
│   │   ├── app.py                 # FastAPI serving alert data + static files
│   │   ├── static/
│   │   │   └── index.html         # Leaflet map + evidence side panel
│   │   └── requirements.txt
│   └── requirements.txt
│
├── scripts/
│   ├── run_all.sh                 # convenience script: docker compose up, then start all 3 pieces
│   ├── seed_terminals.py          # loads static ATM/terminal reference data once
│   └── load_test.py               # ramps producer rate up to demonstrate throughput for the scalability slide
│
└── tests/
    ├── test_schemas.py            # validates sample events against shared/schemas.py
    ├── test_rules.py              # unit tests per detection rule with known fraud/non-fraud graphs
    └── test_integration.py        # smoke test: produce → consume → detect → alert, end-to-end on tiny dataset
```

**Why this layout matters practically:** each workstream is a self-contained folder with its own `requirements.txt`, so a pair can `pip install -r data-generator/requirements.txt` and work without touching or breaking another pair's environment. `shared/schemas.py` is the one file all 3 workstreams import from — it's the actual enforcement mechanism for the contract below, not just documentation.

---

## 6. THE CONTRACT — the 4 JSON schemas (do not drift from these)

### 6.1 Transaction event
**Topic:** `transactions` | **Produced by:** Workstream 1 | **Consumed by:** Workstream 2

```json
{
  "transaction_id": "TXN-8f2a1e",
  "source_account_id": "ACC-00042",
  "target_account_id": "ACC-00891",
  "amount_inr": 15000.0,
  "timestamp": "2026-09-01T10:14:22Z",
  "payment_channel": "UPI | IMPS | NEFT | RTGS | AEPS",
  "device_fingerprint": "hash-string"
}
```
| Field | Type | Notes |
|---|---|---|
| `transaction_id` | string (UUID or prefixed) | globally unique |
| `source_account_id` | string | must match Account node ID pattern `ACC-XXXXX` |
| `target_account_id` | string | same pattern |
| `amount_inr` | float | keep realistic — see §8 amount distribution guidance |
| `timestamp` | ISO-8601 UTC string | used for velocity/window rules |
| `payment_channel` | enum string | affects settlement-time assumptions (see §9) |
| `device_fingerprint` | string (hash) | shared fingerprints across "unrelated" accounts is a core fraud signal |

### 6.2 Account node metadata
**Not streamed on every event** — attached at first-seen, or queryable from graph_store.

```json
{
  "account_id": "ACC-00891",
  "account_tier": "victim | mule_l1 | mule_l2 | aggregator",
  "account_age_days": 12,
  "historical_terminal_ids": ["ATM-001", "ATM-002"]
}
```
`account_tier` is a **ground-truth label your generator assigns**, used to validate your detection rules actually catch what you designed them to catch (and to compute a demo precision/recall number if a judge asks "how accurate is it on your test data").

### 6.3 Terminal/ATM node
**Static reference data, loaded once via `scripts/seed_terminals.py`, not streamed.**

```json
{
  "terminal_id": "ATM-SBI-ND-042",
  "terminal_type": "ATM_KIOSK | AEPS_MICRO_ATM | POS",
  "latitude": 28.5708,
  "longitude": 77.3261,
  "district_pincode": "201301"
}
```
Generate ~30-100 fake terminals spread across a few fake "districts" — this is what your Leaflet map plots.

### 6.4 Risk alert
**Topic:** `risk_alerts` | **Produced by:** Workstream 3 | **Consumed by:** Alert Dispatcher + Dashboard

```json
{
  "complaint_id": "CMP-2026-000451",
  "risk_score": 0.91,
  "flagged_account_id": "ACC-00891",
  "predicted_terminals": [
    {"terminal_id": "ATM-SBI-ND-042", "probability": 0.87, "latitude": 28.5708, "longitude": 77.3261}
  ],
  "evidence": [
    "Shares device fingerprint with known mule cluster",
    "Fan-in of 5 accounts within 3 minutes"
  ],
  "predicted_window_start": "2026-09-01T10:30:00Z",
  "predicted_window_end": "2026-09-01T11:15:00Z"
}
```
`evidence` is a list of **human-readable strings your scorer generates from which rules fired** — this is your "explainability" story, and it should be literally generated from rule names/thresholds, not hand-written per demo case (a judge may ask you to run it live on a new synthetic case).

**Change protocol:** any field add/rename/remove in these 4 schemas gets posted in the group chat *before* you build against it, and `shared/schemas.py` gets updated first so all 3 workstreams' imports stay in sync.

---

## 7. Kafka topic design

| Topic | Partitions | Key | Why |
|---|---|---|---|
| `transactions` | 2-3 | `district_pincode` or `hash(source_account_id)` | Lets you run 2-3 consumers in parallel and show partitioned throughput — this is your literal scalability demo |
| `risk_alerts` | 1 | none needed | Low volume, no need to partition |
| `graph_updates` (optional) | 1 | none | Only add this if Workstream 2 and 3 end up as separate processes that need to communicate over Kafka rather than a shared in-process call. If you're running consumer+scorer in one process for simplicity, skip this topic entirely — don't add complexity you don't need. |

**Simplification if time is short:** it is completely fine for Workstream 2 (graph builder) and Workstream 3 (detection) to run as one combined process that consumes `transactions` and internally calls the scorer after each graph update, publishing straight to `risk_alerts`. The 3-workstream split is about **people and responsibilities**, not necessarily 3 separate running processes. Decide this explicitly as a group on Day 1 — don't let it be ambiguous.

---

## 8. Scalability demonstration — how to actually show this to a judge

You are **not** building a system that ingests real GBs of data. You are building a **small, real, correctly-architected pipeline** and then making a **capacity argument** on top of it. Both parts matter:

1. **Live demo of horizontal scaling (do this):**
   - Run the producer at a configurable rate (start ~50-100 events/sec via `scripts/load_test.py`, ramp up).
   - Show 2 consumer instances (same consumer group) each getting roughly half the partitions' worth of events — this is the actual, undeniable proof that "the architecture scales by adding consumers," which is the whole point of using Kafka at all.
   - Have a terminal window open during the demo showing consumer throughput/lag — visceral and convincing.

2. **Capacity math slide (prepare this, don't skip it):**
   ```
   NCRP reports ~8,000 complaints/day nationally.
   → ≈ 0.09 complaints/sec average, but real-time transaction volume feeding
     the *detection* system is far higher than complaint volume (most
     transactions are legitimate — see PRD "<2% of volume is illicit").
   → Assume national UPI+IMPS volume this system would need to observe:
     (cite NPCI's published UPI transaction/day figures if you have them —
     otherwise state your assumption explicitly, e.g. "X million tx/day").
   → At our local demo throughput of Y events/sec per partition,
     Z partitions × W broker nodes → national volume is achievable by
     horizontal partition scaling, not a redesign.
   ```
   The exact numbers matter less than showing you understand *how* Kafka's partition model is what makes horizontal scaling possible — that's the actual technical literacy a judge is checking for.

---

## 9. Payment channel timing assumptions (for realistic synthetic data + your predicted window field)
- **UPI**: settles in seconds. Real-world fraud cash-out after a UPI transfer can begin within minutes.
- **IMPS**: also near-instant (24x7 interbank).
- **NEFT**: batch-settled (historically half-hourly batches, effectively near-real-time now but still not instant like UPI/IMPS).
- **RTGS**: real-time but generally used for larger amounts (₹2 lakh+) — less common in mule layering chains that use small amounts to stay under scrutiny.
- **AEPS**: relevant specifically for the rural/informal micro-ATM cash-out angle — settlement and physical cash-out can be near-simultaneous at a Business Correspondent point.

**Implication for your generator and your `predicted_window` field:** if your synthetic data uses UPI/IMPS for the digital layering hops, the "45-minute" style window from the original doc is generous — consider generating cash-out windows in the 5-30 minute range for the fast cases, and only wider (hours/days) for the "structuring" evasion cases discussed in Rules.md. Being explicit about this in your pitch (rather than uniformly using one window) is a credibility point.

---

## 10. References & resources
- Kafka docs (concepts, topics/partitions): kafka.apache.org/documentation
- `kafka-python` client: kafka-python.readthedocs.io
- `confluent-kafka` client: docs.confluent.io/kafka-clients/python
- `networkx` docs (graph algorithms, motif/subgraph tools): networkx.org/documentation
- FastAPI docs: fastapi.tiangolo.com
- Leaflet.js docs: leafletjs.com/reference.html
- AMLSim (IBM's synthetic AML transaction generator — the reference architecture your generator should take inspiration from for realistic fan-in/fan-out/layering patterns and power-law amount distributions): github.com/IBM/AMLSim
- NCRP (National Cybercrime Reporting Portal) — cite as your real-world complaint-volume source: cybercrime.gov.in
- RBI MuleHunter.AI — search "RBI MuleHunter.AI pilot" for the official press coverage; cite as the real, already-deployed account-detection precedent your system extends.
- I4C (Indian Cybercrime Coordination Centre) — reference for JCCT/coordination-layer framing.
