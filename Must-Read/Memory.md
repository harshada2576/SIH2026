# Memory.md — Running Progress Log
### SIH26184 — Predictive Cash Egress Interception
**Status: starts empty, grows as you build. This is the file that stops your AI tool from wasting tokens re-reading the whole codebase or making things up when you switch chats/sessions.**

---

## Why this file matters more than it looks like it does
When you close an AI chat session and open a new one tomorrow (or switch tools mid-project), the new session has zero memory of what you built, what worked, and what you already tried and rejected. Without this file, you'll either (a) paste huge chunks of code back in every time to re-establish context, burning time and tokens, or (b) let the AI guess/re-derive decisions, which often produces subtly different code than what you already have. Pasting the last few entries of this file at the start of a new session fixes both.

## How to use it
- Each pair keeps their own copy of this file (or a section in the shared one — pick whichever your team prefers) and updates it **at the end of each work session**, not just once a day.
- Keep entries short — a few lines. This is a changelog for an AI's context window, not a diary.
- When starting a new AI chat session, paste in your last 1-3 entries as your first message, e.g.: *"Here's where we left off: [paste entries]. Continue from here, don't re-derive the schema, use shared/schemas.py as-is."*

## Entry format
```
### [Date] [Time, optional] — [Workstream name]
- What we built/changed:
- Current state (what works, what's broken/untested):
- Blockers / waiting on:
- Next step:
```

## Example (illustrative — delete once real entries start)
```
### Aug 29, 11pm — Data Generator
- What we built/changed: generate.py produces 500 normal transactions matching schemas.py; producer.py publishes them to "transactions" topic successfully, confirmed via console consumer.
- Current state: normal traffic generation works end-to-end. No fraud patterns injected yet — that's tomorrow.
- Blockers: none right now.
- Next step: implement fan-out injection in patterns.py, tune amount distribution to power-law per AMLSim reference.
```

---

## Log

### Aug 29, 2026 — Workstream 3: Heuristic Scorer (dash agreed to be separate)
- What we built/changed (skeleton was 100% empty — greenfield, branch `feature/heuristic-scorer-android-dashboard`):
  - `shared/schemas.py` initialized EXACTLY per Architecture.md §6 (4 pydantic models + PredictedTerminal). Account-id regex relaxed to `ACC-[A-Za-z0-9]+` (still the ACC-XXXXX pattern) — nothing else drifted. **SCHEMA OWNERS: review this file first; it is now the contract.**
  - `pipeline/graph_store.py`: minimal networkx wrapper implementing the documented API the rules read (`add_transaction`, `add_account_metadata`, `get_neighborhood`, `fan_in_count`, `fan_out_count`, `unique_*`, `accounts_sharing_device_fingerprint`, `trail_depth`, `edge_latency_between`, `forwarded_transactions`, `historical_terminal_ids`). **Stand-in for WS2's live Kafka-fed store — WS2 owns/evolves; flag if API shape needs changing.**
  - `detection/rules/*`: 8 independently-testable rules (fan_in, fan_out, velocity, layering, amount_movement, account_age, device_fingerprint, terminal_affinity) + `base.py` (RuleResult). Each returns severity 0..1; scorer multiplies by weight.
  - `detection/scorer.py`: `WEIGHTS` sum to exactly 100 (matches brief: vel20/fan-in20/fan-out10/layer15/amount15/age5/device5/history10); bands LOW<30 / MED 30-59 / HIGH 60-79 / CRITICAL 80-100; `evaluate_account`, `predict_window` (channel-aware UPI/IMPS/AEPS/NEFT/RTGS), `reconstruct_trail` (greedy largest-leg), `analyze` → RiskAlert with evidence auto-generated from rules that fired; alert threshold ≥60.
  - `detection/terminal_ranking.py`: `rank_terminals` → 0-100 PRIORITY per terminal (history 30 / distance 20 / time-pattern 15 / type 10 / network-assoc 15 / district 10). Framed as priority, NOT calibrated probability (schema field stays `probability` per locked contract).
  - `detection/alert_dispatcher.py`: console stub only (no Kafka yet — per brief). Signature already takes `kafka_topic`; wiring the real producer into it is integration-day work. Reconfigures stdout to UTF-8 (₹ renders on Windows).
  - `scripts/seed_terminals.py` → `shared/terminals.json` (30 fictional terminals, 3 fake districts, deterministic seed) — scorer loads it via `load_terminals()`.
### Aug 30, 2026 — Frontend Mandate & Android Testing
- Architecture Clarification: Confirmed that **CyberShield Native Android App (`CyberShield/`)** is the SOLE frontend for the project. Removed unused HTML web dashboard files (`detection/dashboard/*`).
- Updated all documentation (`AGENTS.md`, `Must-Read/Rules.md`, `Must-Read/Architecture.md`, `Must-Read/Design.md`, `Must-Read/PRD.md`) so all agents and team members remain aligned on the single Kotlin + Jetpack Compose Android client.
- Python backend tests: `python -m pytest` -> 24 passed (100%).
- Android project: `CyberShield/` contains the native Kotlin Jetpack Compose app with Radar Google Maps, Investigation XAI drawer, Dispatch queue, and Auth screens.
- Next step: Build and test CyberShield Android Kotlin app using Gradle.
