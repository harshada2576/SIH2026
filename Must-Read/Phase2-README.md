# CyberShield — Phase 2 additions (Sept 2026 sprint, pre-Sept 5 internal hackathon)

This layer was added on top of the existing 8-rule detection engine + Android
app without touching the locked contracts (`shared/schemas.py`'s
`TransactionEvent`/Kafka topic fields, Architecture.md §6.1). Everything here
is additive: existing code, tests, and the Android app keep working exactly
as before.

## What's new

### 1. Three new detection rules (now 11 total, weights rebalanced to sum to 100 — see `detection/scorer.py`)

| Rule | File | What it catches |
|---|---|---|
| `geo_velocity` | `detection/rules/geo_velocity_rule.py` | Physically-impossible travel between two cash-out locations (the "lives in Mumbai, card used in Hyderabad 40 min later" case) |
| `identity_cluster` | `detection/rules/identity_cluster_rule.py` | Many accounts opened under one shared KYC identity — the "12–20 mule accounts on one stolen identity" pattern |
| `ml_anomaly` | `detection/rules/ml_anomaly_rule.py` | Unsupervised IsolationForest outlier score vs. the current account population — the "hybrid rule + ML" layer, with a z-score fallback if the population is too small or scikit-learn isn't installed |

`geo_velocity` reads from a **new, separate** `GraphStore.record_terminal_usage()` /
`recent_terminal_usages()` timeline — deliberately NOT from the locked
transaction schema, so nobody else's code has to change.
`identity_cluster` reads a new **optional** `kyc_identity_id` field on
`AccountNodeMetadata` (defaults to `None`, so every existing CSV/dict still
loads fine).

### 2. Confidence scoring — `detection/confidence.py`
Every alert now carries an optional `confidence` field (0–1): 60% rule-agreement
breadth + 40% the ML rule's own severity. This is what lets automated response
tell "CRITICAL but only one rule fired" apart from "CRITICAL and everything agrees."

### 3. Tiered automated response — `detection/auto_intervention.py`
Answers "should blocking be automatic?" with a tiered answer instead of a single
switch (see the file's docstring for the reasoning):

| Band | Confidence | Action |
|---|---|---|
| CRITICAL | HIGH | **Automatic freeze** + LEA notify |
| CRITICAL | not HIGH | **Automatic hold** (reversible) + LEA notify |
| HIGH | any | Soft notify to bank + LEA notify, no funds action |
| MEDIUM/LOW | any | Logged only |

Every decision — action taken or not — gets an explicit justification string,
written to stdout, the SQLite store, and the signed audit ledger.

### 4. Mock Bank + NCRP/I4C APIs — `mock_services/`
Zero-dependency (Python stdlib `http.server`, no pip installs needed) fake
services so "automatic bank action" and "interoperability" are real, callable
HTTP calls in the demo instead of a claim:

```
python -m mock_services.bank_api.server        # port 8001, simulates HDFC-SIM/ICICI-SIM/SBI-SIM
python -m mock_services.ncrp_i4c_api.server     # port 8002, returns a case number + assigned unit
```

**Be honest about this in Q&A**: these are demo stand-ins, not real bank/NCRP
integrations — no hackathon team can get that access, and claiming otherwise
would hurt credibility, not help it.

### 5. Signed, tamper-evident audit ledger ("blockchain-lite") — `audit/`
Not a real permissioned blockchain (Hyperledger Fabric is the honest target-
production answer — see Phases.md roadmap). What this gives you for real:
every alert/decision is hashed, chained to the previous hash, and signed with
an Ed25519 key generated on first run. `verify()` catches a tampered payload,
a deleted/reordered block, or an invalid signature.

**Live demo**: `python -m audit.tamper_demo` — appends 4 signed alerts,
verifies (clean), tampers with one payload directly on disk, verifies again
(tamper detected, exact block flagged). This is the "watch us tamper with a
record" stage moment.

### 6. SQLite persistence — `shared/persistence.py`
Every alert + intervention decision is now durably logged (`data/output/cybershield.db`),
not just printed to console — the minimal "database architecture" a
prototype needs to prove replay/audit without standing up Postgres/Neo4j.

## Running everything

```bash
# terminal 1
python -m mock_services.bank_api.server
# terminal 2
python -m mock_services.ncrp_i4c_api.server
# terminal 3 — the actual demo
python -m scripts.demo_phase2
```

`scripts/demo_phase2.py` builds three scenarios entirely in-memory (no Kafka/
Docker needed, so it can't fail on stage for infra reasons):

1. A 12-account mule identity ring (shared KYC id) — lands in HIGH band, triggers `SOFT_NOTIFY`.
2. A Mumbai→Hyderabad geo-velocity case — demonstrates the new rule directly.
3. A saturated multi-signal case — lands in CRITICAL band with HIGH confidence, triggers `AUTO_FREEZE`.

Then:
```bash
python -m audit.blockchain_lite verify     # confirm the real ledger from the demo run is clean
python -m audit.tamper_demo                # the tamper-detection stage moment (separate demo ledger)
curl http://localhost:8001/accounts        # see which accounts got frozen/held/notified, and by which simulated bank
curl http://localhost:8002/alerts          # see LEA acknowledgements + case numbers
```

Existing tests still pass unchanged; new coverage:
```bash
pytest tests/test_phase2_rules.py tests/test_phase2_audit_and_intervention.py -v
```

## What's still honestly slide-only (do not claim these are built)

- **Apache Flink / distributed stream processing** — kept on Kafka + the
  existing Python consumer + NetworkX. A Flink migration is weeks of work for
  a team that hasn't used it; attempting it before Sept 5 risks the whole
  working pipeline.
- **Real multi-bank live transaction ingestion** — no hackathon team can get
  this access. The mock Bank API plays the same role for the demo.
- **Real NCRP/I4C integration** — same reasoning; the mock service plays the role.
- **A real permissioned blockchain (Hyperledger Fabric)** — blockchain-lite
  gives you the actual property judges care about (tamper-evidence + signed
  provenance) without a multi-week infra project.
- **Production auth/RBAC, security audit, legal sign-off for automated
  freezes** — out of scope for any hackathon prototype; say so plainly if asked.

Put these on one architecture/roadmap slide, named honestly as "target
production architecture," not "already built."
