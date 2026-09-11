# PRD.md — Product Requirements Document
### SIH26184 — Predictive Cash Egress Interception
**Status: LOCKED (scope + success criteria). This defines "done" so 6 people don't drift toward 6 different interpretations of the project.**

---

## 1. One-liner
A prototype that ingests a stream of financial transactions, detects mule-account fraud patterns (fan-in / fan-out / layering) using a graph-aware, explainable heuristic engine, and predicts + alerts on the likely physical cash-out location before withdrawal happens — architected on Kafka to demonstrate the pipeline scales to real transaction volumes.

## 2. Problem statement (full version, for the deck's problem slide)
Cybercrime proceeds in India move through chains of "mule" bank accounts — often opened using stolen or purchased identities — in a matter of minutes, and are withdrawn as physical cash at an ATM or informal AEPS micro-ATM point before banks or police have any actionable signal. The existing national mechanism, CFCFRMS (Citizen Financial Cyber Fraud Reporting and Management System), can freeze accounts and has recovered significant sums — but it is fundamentally **reactive**: it acts only after a victim files a complaint through NCRP (National Cybercrime Reporting Portal), by which point the physical cash-out has frequently already happened. Our system is **proactive**: instead of only asking "which account is suspicious," it asks "given the shape of this transaction graph right now, where and when will this money become untraceable cash — and can we get ahead of that moment."

## 3. Real-world numbers to ground this (memorize these for Q&A)
| Number | Value | Source note |
|---|---|---|
| NCRP daily complaints | ~8,000/day | cite NCRP / I4C published figures |
| Cumulative reported losses | ₹56,000+ crore | cite I4C/NCRP annual figures |
| CFCFRMS amount saved via freezes | ₹11,000+ crore | cite official I4C reporting |
| Estimated illicit share of transaction volume | <2% | this is *why* naive single-rule classifiers fail — the base rate is so low that a poorly-tuned system either misses fraud or drowns analysts in false positives |

**Be ready to say where these numbers came from if asked** — don't present government statistics without being able to name the source (I4C/NCRP/RBI). If you're not 100% sure of an exact figure by presentation day, round conservatively and say "on the order of."

## 4. Target users / personas (for framing your solution slide and Q&A)
| Persona | What they need from this system | What they currently have |
|---|---|---|
| Law Enforcement Agency (LEA) / JCCT (Joint Cyber Coordination Team) officer | Terminal-level, time-bound alert with enough evidence to justify dispatching a patrol or contacting a bank branch | Account-level freeze requests via CFCFRMS, after-the-fact |
| Bank fraud/compliance analyst | Account-level risk flag with explainable evidence, to decide whether to place a hold | Static rule-based monitoring (per the doc's own framing), or newer ML tools like MuleHunter.AI at account level only |
| (For this prototype) Judges/evaluators | Clear evidence of detection working, an alert firing, and a credible scalability argument, end-to-end, live | — |
| (Stretch — mention, don't build) The victim/complainant (1930 caller) | Visibility that their case is being actively worked, not just filed | Currently mostly a black box after filing a complaint |

## 5. In scope for the Sept 1 prototype (build exactly this, nothing more)
1. **Synthetic data generator** — realistic normal transaction traffic + injected fraud patterns (fan-out, fan-in, layering chains, triadic/circular motifs), following AMLSim-style power-law amount distributions.
2. **Kafka-based ingestion pipeline** — producer publishes transaction events to a partitioned topic; consumer(s) build/update an in-memory graph in real time.
3. **Detection engine** — explainable rule/heuristic scorer (fan-in ratio, dormancy-then-burst, device fingerprint reuse, forwarded-fund proportion, terminal affinity) — **not** a trained GNN.
4. **Alerting** — a triggered notification (console log and/or webhook/email stub) when a risk threshold is crossed.
5. **CyberShield Android App (Frontend)** — Native Kotlin + Jetpack Compose mobile command dashboard showing flagged accounts, ranked predicted terminals with confidence scores on Google Maps, and explainable evidence trail per alert.
6. **Scalability story** — a live demonstration of partitioned throughput (2-3 consumers) plus a one-slide capacity/throughput argument extending the local numbers to national scale.
7. **SMS & Email Notification Subsystem (Sprint 4)** — Multi-channel notifications for bank, security, and investigation teams across critical fraud lifecycle events (high-risk detection, confirmed fraud, cashout attempt, withdrawal blocked, police alert dispatched) with SQLite persistence and native Android UI delivery tracking.

## 6. Explicitly out of scope (state this confidently in the pitch — it's a strength, not an apology)
- Real bank data or any real PII of any kind.
- A trained GNN/GAT/TGN model — heuristics/rules are used instead; the trained-model architecture is presented as **target/future work** with the math formulation on a separate "roadmap" slide.
- Web HTML/JS dashboard — CyberShield Native Android App (`CyberShield/`) is the sole designated frontend.
- A production-grade multi-broker Kafka cluster — single local broker demonstrating the correct partitioning *pattern* is sufficient; extrapolation to production scale is a math slide, not a build task.
- Real legal/regulatory integration, real police/bank API integration, real I4C/JCCT system integration.
- Authentication, user accounts, production security hardening — irrelevant to a local prototype demo.
- Terabyte-scale datasets — dataset stays in the low-thousands-to-tens-of-thousands of synthetic transactions range (see Rules.md).

## 7. Functional requirements
| ID | Requirement | Owned by |
|---|---|---|
| FR1 | Generator produces valid transaction events matching the Architecture.md schema | Workstream 1 |
| FR2 | Generator injects at least 3 distinct fraud pattern types (fan-in, fan-out, layering) at a configurable rate | Workstream 1 |
| FR3 | Generator assigns ground-truth `account_tier` labels so detection accuracy can be measured | Workstream 1 |
| FR4 | Producer publishes to Kafka topic `transactions`, partitioned as defined in Architecture.md | Workstream 1 |
| FR5 | Consumer(s) build and continuously update an in-memory graph from consumed events | Workstream 2 |
| FR6 | Graph store exposes queryable functions (fan-in count, neighborhood lookup, device fingerprint overlap) | Workstream 2 |
| FR7 | At least 4 independent heuristic rules run against the graph and combine into a single risk score | Workstream 3 |
| FR8 | Alerts crossing threshold are published to `risk_alerts` with populated `evidence` array | Workstream 3 |
| FR9 | CyberShield Android App renders flagged accounts/terminals on Google Maps with risk-based color coding | Workstream 3 |
| FR10 | CyberShield Android App shows the evidence trail (which rules fired) per alert, on click/select | Workstream 3 |
| FR11 | System demonstrably runs 2+ Kafka consumers in the same consumer group in parallel | Workstream 2 |

## 8. Non-functional requirements
| ID | Requirement |
|---|---|
| NFR1 | End-to-end pipeline (generate → publish → consume → detect → alert → display) must run on a single laptop with no external cloud dependency, for demo reliability |
| NFR2 | Each component fails loudly and locally rather than silently dropping events or crashing the whole pipeline |
| NFR3 | Dataset generation completes in well under a few minutes locally (if it's slower, it's too big for this timeline) |
| NFR4 | CyberShield Android UI is legible from the back of a presentation room (large fonts, high contrast, minimal clutter) |
| NFR5 | The full demo can be run from a clean checkout with a documented set of commands (`README.md` + `scripts/run_all.sh`) — don't rely on undocumented manual setup steps only one teammate remembers |

## 9. Success criteria
- **By Sept 1 (prototype freeze):** data generator → Kafka → consumer/graph → detection → alert → CyberShield Android App all wired together and running end-to-end on one machine, on a small dataset, live and repeatable.
- **By Sept 4 (presentation):** the above, plus a rehearsed 3-minute demo script, a scalability/capacity slide, an architecture slide (including the future-work GNN/production stack as "target architecture," not as something you claim to have built), and rehearsed answers from the Q&A prep checklist.

## 10. How this differs from what already exists (have this exact answer ready)
- **RBI's MuleHunter.AI** already does ML-based *account-level* mule detection in production, piloted in two public sector banks. We are not reinventing that — we assume an equivalent detection layer exists or could feed into ours, and we extend one layer further: from "which account is suspicious" to "where and when will the money become physical cash." This is the genuinely under-explored gap (see the earlier viability discussion in this thread).
- **CFCFRMS** freezes accounts reactively, after a complaint. We propose feeding it (or an equivalent LEA/JCCT workflow) *earlier, more targeted* intelligence, so intervention can happen at the terminal/time level rather than only at the account level, after the fact.
- **I4C/JCCT** already exists as the cross-jurisdiction coordination layer. We are not proposing to replace it or reinvent jurisdictional coordination — we're proposing to feed better, earlier signal into a coordination mechanism that already exists.

## 11. Known risks / open questions (own these proactively in the pitch)
| Risk | Mitigation to state in pitch |
|---|---|
| False positives → denying legitimate customers access to an ATM | Tiered response: soft alert to patrol at lower confidence, hard freeze recommendation only above a high threshold — never a blanket automated terminal shutdown |
| Banks/NPCI reluctance to share data | Frame as an I4C-hosted neutral intermediary model, not bank-to-bank data exposure |
| Predicted time window may be too generous vs real UPI/IMPS speed | Use realistic (minutes-scale) windows for fast digital rails; explicitly show a wider window only for "structuring"-style slow evasion cases (see Rules.md / Architecture.md §9) |
| Fraudsters adapt once patterns are known (adversarial drift) | Present as a system with a retraining/feedback loop by design, not a static solved model — see the adversarial drift discussion already had in this project's ideation thread |
| Detection lag during the report → label → retrain cycle | Layered defense: rules backstop + unsupervised anomaly detection + fast-track labeling + confidence-tiered routing, so the system isn't relying on a single always-current model |

## 12. References
- NCRP: cybercrime.gov.in
- I4C (Indian Cybercrime Coordination Centre)
- RBI MuleHunter.AI — search official RBI/press coverage of the pilot
- AMLSim (IBM) — reference generator for realistic AML transaction patterns: github.com/IBM/AMLSim
- PMLA (Prevention of Money Laundering Act) — background reading for "structuring" / layering terminology used throughout these docs
