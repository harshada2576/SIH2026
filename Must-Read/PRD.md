# PRD.md — Predictive Cash Egress Interception (SIH26184)

## One-liner
A prototype that ingests a stream of financial transactions, detects mule-account fraud patterns (fan-out/fan-in/layering) using a graph-aware heuristic engine, and predicts+alerts on likely physical cash-out locations before withdrawal happens — demonstrated at scale using Kafka.

## Problem (condensed)
Cybercrime proceeds move through mule account chains in minutes and are withdrawn as physical cash before banks/police can freeze anything. Existing systems (CFCFRMS) freeze accounts *after* a complaint is filed — reactive. We predict *where* and *when* physical cash-out will happen, so intervention can happen before the money disappears.

## Target users (for this prototype's framing)
- Law enforcement agencies (LEAs) / JCCT units — receive terminal-level alerts
- Bank fraud/compliance teams — receive account-level flags
- (Judges/evaluators) — need to see detection, alerting, and scalability demonstrated end-to-end

## In scope for the Sept 1 prototype
1. **Synthetic data generator** — produces a stream of transactions with realistic normal traffic + injected fraud patterns (fan-out, fan-in, layering chains, triadic motifs).
2. **Kafka-based ingestion pipeline** — producer publishes transaction events; consumer(s) build/update an in-memory or lightweight graph store in real time.
3. **Detection engine** — rule/heuristic-based scorer (NOT a trained GNN) that flags accounts and predicts likely cash-out terminals based on graph structure + historical terminal affinity in the synthetic data.
4. **Alerting** — a triggered notification (console log, webhook, or simple email/SMS stub) when a high-risk pattern + predicted terminal crosses a threshold.
5. **Dashboard** — a map/GIS view showing flagged accounts, predicted terminals with confidence scores, and the evidence trail (which transactions triggered the flag).
6. **Scalability story** — the pipeline should demonstrably handle a synthetic load significantly larger than a single script could process serially (this is the point of using Kafka at all), plus a one-page capacity/throughput argument for how it extends to national scale.

## Explicitly out of scope (say this confidently, don't apologize for it)
- Real bank data or any real PII.
- A trained GNN/GAT/TGN model — we use explainable heuristics/rules instead, and present the GNN architecture as target/future work.
- A production-grade multi-broker Kafka cluster — a single-broker local setup demonstrating the correct pattern is sufficient.
- Legal/regulatory integration, real police/bank API integration.
- Authentication, user accounts, or any production security hardening — not needed for a prototype demo.

## Success criteria
- **By Sept 1**: data generator → Kafka → consumer → detection → alert → dashboard all wired together and running end-to-end on one machine, even with a small dataset.
- **By Sept 4**: the above plus a rehearsed 3-minute demo, a capacity/scalability slide, and answers ready for the Q&A prep list.

## Key numbers to reference in the pitch
- ~8,000 NCRP complaints/day; ₹56,000+ crore cumulative losses; CFCFRMS has saved ₹11,000+ crore via freezes.
- <2% of real transaction volume is illicit — this is why naive classifiers fail and why we need pattern/graph-based detection.
