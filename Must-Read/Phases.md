# Phases.md — Rough Timeline (edit freely, this is a starting skeleton)

Aug 28 → Sept 4. Add/move/rename phases as your workstream actually needs — this is a suggested shape, not a locked schedule. Update it as things progress so anyone checking knows where things stand.

## Phase 1 — Foundations (Aug 28-29)
- [ ] Everyone aligned on Architecture.md schemas
- [ ] Data generator: basic transaction generation working (even without fraud patterns yet)
- [ ] Kafka pipeline: local broker running, producer/consumer can send and receive a test message
- [ ] Detection/dashboard: skeleton FastAPI app + blank map rendering

*(add/edit sub-tasks per workstream here as you go)*

## Phase 2 — Core functionality (Aug 30-31)
- [ ] Data generator: fraud patterns (fan-out, fan-in, layering) injected
- [ ] Kafka pipeline: graph store actually updating live from consumed events
- [ ] Detection: heuristic scoring producing real risk_alert output

*(edit freely)*

## Phase 3 — Integration (Sept 1) — prototype freeze target
- [ ] All 3 pieces wired end-to-end, running together
- [ ] Fix whatever breaks when pieces actually talk to each other

## Phase 4 — Polish + scale demo (Sept 2-3)
- [ ] Scalability demonstration (multiple partitions/consumers, throughput numbers)
- [ ] Dashboard visual pass
- [ ] Deck + demo script rehearsal

## Phase 5 — Presentation (Sept 4)

*(Feel free to restructure this entire file — split phases per-workstream instead of shared, add dates, whatever helps your pair track progress. The only thing that matters is Architecture.md's contract stays honored.)*
