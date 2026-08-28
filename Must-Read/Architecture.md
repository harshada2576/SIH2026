# Architecture.md — Interface Contract Between Workstreams

**Read this before opening any AI coding session.** This file exists so 3 pairs building independently produce code that actually connects on Sept 1. If you need to change anything in here, message the group first — don't just change it in your own branch.

## High-level flow

```
[Workstream 1: Data Generator]
        |  publishes JSON events
        v
   Kafka topic: "transactions"
        |
        v
[Workstream 2: Kafka Consumer + Graph Builder]
        |  maintains in-memory/lightweight graph store
        |  exposes current graph state + new-event stream
        v
[Workstream 3: Detection Engine]
        |  reads graph state, runs heuristic scoring
        |  outputs risk_alert JSON (below) when threshold crossed
        v
   [Alert Dispatcher]  +  [Dashboard]
   (console/webhook/       (map + evidence view,
    email stub)             reads risk_alert stream)
```

## Tech stack (locked — don't let your AI tool swap these)
- **Language**: Python 3.11+ everywhere, for consistency across all 3 workstreams.
- **Kafka**: local single-broker setup via Docker (`confluentinc/cp-kafka` image) or `kafka-python` / `confluent-kafka` client library.
- **Graph store**: `networkx` in-memory graph (do NOT stand up Neo4j — unnecessary complexity for a 3-day prototype).
- **Backend/API**: FastAPI (lightweight, easy for dashboard to poll or receive pushed data).
- **Dashboard/frontend**: a single HTML page with Leaflet.js (CDN import, no build step) — keep it simple.
- **Data format**: JSON everywhere. No binary formats, no Avro/Protobuf — not worth the setup time this week.

## Folder structure

```
/data-generator/       # Workstream 1
    generate.py
    patterns.py         # fan-out, fan-in, layering injection logic
    producer.py          # publishes to Kafka topic "transactions"

/pipeline/              # Workstream 2
    consumer.py          # reads "transactions", updates graph
    graph_store.py       # networkx wrapper, exposes query functions

/detection/             # Workstream 3
    scorer.py            # heuristic rules, reads graph_store
    alert_dispatcher.py  # publishes to topic "risk_alerts" or webhook
    dashboard/
        app.py           # FastAPI serving alert data
        index.html       # Leaflet map + evidence panel

/shared/
    schemas.py           # the JSON schemas below, as one shared source of truth
```

## THE CONTRACT — exact schemas (this is the part that must not drift)

### 1. Transaction event (published to Kafka topic `transactions`)
```json
{
  "transaction_id": "uuid-string",
  "source_account_id": "string",
  "target_account_id": "string",
  "amount_inr": 15000.0,
  "timestamp": "2026-09-01T10:14:22Z",
  "payment_channel": "UPI | IMPS | NEFT | RTGS | AEPS",
  "device_fingerprint": "hash-string"
}
```

### 2. Account node metadata (can be attached to first-seen accounts, or looked up)
```json
{
  "account_id": "string",
  "account_tier": "victim | mule_l1 | mule_l2 | aggregator",
  "account_age_days": 12,
  "historical_terminal_ids": ["ATM-001", "ATM-002"]
}
```

### 3. Terminal/ATM node (static reference data, loaded once, not streamed)
```json
{
  "terminal_id": "string",
  "terminal_type": "ATM_KIOSK | AEPS_MICRO_ATM | POS",
  "latitude": 28.5708,
  "longitude": 77.3261,
  "district_pincode": "201301"
}
```

### 4. Risk alert (published by Workstream 3, consumed by dashboard + alert dispatcher)
```json
{
  "complaint_id": "string",
  "risk_score": 0.91,
  "flagged_account_id": "string",
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

**Rule: nobody adds/renames/removes a field in these 4 schemas without posting it in the group chat first.** If workstream 3 needs a field workstream 2 isn't providing, that's a 30-second message, not a silent local patch.

## Scalability demonstration approach
- Run the producer at a configurable rate (start at ~50-100 events/sec, push higher to show it holds).
- Use 2-3 partitions on the `transactions` topic, keyed by `district_pincode` or a hash of `source_account_id`, so you can show parallel consumers — this is your actual "scalability" evidence, not the raw data volume.
- Prepare one slide translating this local demo into national-scale math (see PRD numbers): X events/sec locally × partition math → estimated capacity for NCRP's real complaint volume.
