# Phases.md — Timeline & Checklist
### SIH26184 — Predictive Cash Egress Interception
**Status: EDITABLE. Restructure freely — split per-workstream, add dates, whatever helps your pair track progress. The one thing that must stay honored is Architecture.md's schema contract.**

Today is **Aug 28**. Prototype freeze target is **Sept 1**. Presentation is **Sept 4**.

---

## Phase 0 — Tonight (Aug 28, evening)
**Goal: everyone opens their AI coding session tomorrow already aligned, so no two pairs build incompatible assumptions.**
- [ ] Whole team reads Architecture.md together (or at least skims the 4 schemas + folder structure) — 15 minutes, non-negotiable.
- [ ] Confirm the workstream split (who's on Data Generator / Kafka Pipeline / Detection + CyberShield Android App) and post it in the group chat.
- [ ] Confirm the tech stack decisions in Architecture.md are agreed — especially `kafka-python` vs `confluent-kafka`, since both pairs touching Kafka need to use the same one.
- [ ] Decide as a group: is Workstream 2 (graph builder) and Workstream 3 (detection) one combined process or two separate ones communicating over an extra Kafka topic? (See Architecture.md §7 — pick the simpler option unless there's a good reason not to.)
- [ ] Repo created, folder skeleton from Architecture.md §5 pushed, `docker-compose.yml` for local Kafka added.

## Phase 1 — Foundations (Aug 29)
**Goal: each workstream has the dumbest possible version of their piece running standalone, before adding fraud logic/intelligence.**

| Workstream | Tasks |
|---|---|
| Data Generator | [ ] `generate.py` produces N random *normal* transactions matching the schema (no fraud patterns yet) · [ ] `producer.py` successfully publishes them to the `transactions` topic · [ ] Can tune event rate via config |
| Kafka Pipeline | [ ] Local Kafka broker running via `docker-compose up` · [ ] `consumer.py` can read the test messages from Workstream 1 and print them · [ ] `graph_store.py` skeleton: can add a node/edge from a transaction event |
| Detection + CyberShield App | [ ] FastAPI backend REST server running (`/health` endpoint at minimum) · [ ] CyberShield Android Kotlin app rendering MapLibre OSM radar map · [ ] `scorer.py` skeleton exists (returning explainable risk score) |

**End-of-day checkpoint:** can you run all 3 pieces at once (even disconnected) without errors? If not, that's tomorrow's first task, not something to carry into Phase 2.

## Phase 2 — Core functionality (Aug 30-31)
**Goal: real logic, still tested standalone per workstream — integration comes in Phase 3.**

| Workstream | Tasks |
|---|---|
| Data Generator | [ ] `patterns.py`: implement fan-out injection (one account sends to many) · [ ] implement fan-in injection (many accounts send to one) · [ ] implement layering chains (A→B→C→D, decreasing/splitting amounts) · [ ] assign ground-truth `account_tier` labels as patterns are injected · [ ] tune amount distribution to be power-law-ish, not uniform random (see AMLSim reference in Architecture.md) |
| Kafka Pipeline | [ ] Graph store actually updates live as events stream in, not just on a test message · [ ] Implement query functions: `fan_in_count(account_id, window)`, `get_neighborhood(account_id)`, `shared_device_fingerprint(account_id)` · [ ] Partition the `transactions` topic (2-3 partitions) and confirm a second consumer can join the same consumer group |
| Detection + CyberShield App | [ ] Implement at least 4 independent rules in `detection/rules/` (fan-in, velocity/dormancy-burst, device fingerprint reuse, terminal affinity) · [ ] Combine rule outputs into a single `risk_score` · [ ] Generate the `evidence` array directly from which rules fired (not hardcoded text) · [ ] Publish real `risk_alert` events to the `risk_alerts` topic · [ ] CyberShield Android App syncs with backend and plots real points on the radar map |

**End-of-day checkpoint (Aug 31):** each workstream's *own* piece works correctly on its own test data. Don't start integration debugging with pieces that aren't individually solid yet.

## Phase 3 — Integration (Sept 1) — PROTOTYPE FREEZE TARGET
**Goal: all 3 pieces wired together, running as one system, end-to-end, on one machine.**
- [ ] Full pipeline runs from a single command (`scripts/run_all.sh` or documented manual steps): generator → Kafka → consumer/graph → detection → alert → CyberShield Android App.
- [ ] Run it live, watch a fraud pattern get generated, flow through, and surface as a real alert on the map with real evidence text.
- [ ] Fix whatever breaks when the pieces actually talk to each other for the first time (expect this — budget the whole day for it, don't be surprised by it).
- [ ] Freeze scope here. Anything not working by end of today gets cut from the demo script, not force-fixed at 2am before presentation prep starts.

## Phase 4 — Polish + scale demo (Sept 2-3)
**Goal: turn a working prototype into a convincing, rehearsed presentation.**
- [ ] Run `scripts/load_test.py` to demonstrate throughput scaling with 2 consumers — capture a screen recording as backup in case live demo has issues on presentation day.
- [ ] Build the capacity/scalability math slide (Architecture.md §8).
- [ ] CyberShield Android App visual pass — color coding, legibility from back of room (Design.md).
- [ ] Architecture/target-stack slide (STGNN math, Kafka-Flink-Neo4j production vision) — presented explicitly as roadmap, not built.
- [ ] Deck assembled, using the original doc's 3-minute demo script structure as the backbone.
- [ ] Full run-through rehearsal, timed to 3 minutes.
- [ ] Q&A prep — go through the checklist doc (SIH26184 prep checklist) as a team, assign one confident owner per topic area (GNN, MuleHunter.AI/existing systems, legal/regulatory, infra, adversarial evasion).

## Phase 6 — Sprint 4: SMS & Email Notification Subsystem (Sept 11)
- [x] Implement modular `NotificationService` supporting 7 critical lifecycle events.
- [x] Provide mock providers with explicit `[SIMULATED]` labeling and configuration for real SMS/SMTP gateways.
- [x] Add SQLite persistent storage (`cybershield.db -> notifications`) with deterministic idempotency.
- [x] Implement bounded retry mechanism (up to 3 retries) with graceful degradation.
- [x] Expose backend endpoints: `GET /cases/{case_id}/notifications` and `POST /cases/{case_id}/notify`.
- [x] Integrate `NotificationDeliveryCard` into CyberShield Native Android `CaseDetailScreen`.
- [x] Validate complete test suite (127 passed) and operational demo script.
