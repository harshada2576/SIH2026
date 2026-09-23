# SIH2026 Final Demo Rehearsal — C

## Purpose

C is the **final rehearsal before recording** the SIH2026 demo videos.

The PPT is the presentation/story reference. The repository implementation is the source of truth.

The demo uses **one physical Android phone only**.

The objective is to prove the complete operational story:

**DETECT → TRACE → PREDICT CASH-OUT → PRIORITIZE → INTERVENE → ESCALATE → AUDIT**

## Selected A2 Scenario

**The High-Velocity Mule Layering & Cash-Out Interception Incident**

The rehearsal successfully demonstrated:

- live suspicious activity generation
- real backend processing
- live WebSocket delivery to the physical Android device
- bank investigation
- risk/evidence
- money trail
- selective fund protection
- cash-out prediction
- terminal/location evidence
- police escalation
- police-side workflow
- audit evidence

Two clean runs were completed successfully with no runtime crashes, networking dropouts, or database concurrency failures.

## Critical Live Path

The demo must visibly establish:

```text
Backend
  ↓
Cloudflare / public Internet
  ↓
WebSocket
  ↓
ONE physical Android phone
  ↓
CyberShield UI update
```

No `adb reverse`, `adb forward`, USB application tunnel, or LAN-only dependency is permitted.

The public endpoint is:

- `https://sih.seucra.tech`
- `wss://sih.seucra.tech/ws`

Canonical backend port: **5003**.

## One-Phone Role Model

There is only one CyberShield phone.

### Bank Official

- receives the live incident
- opens the case
- reviews risk/evidence
- inspects money trail
- protects suspicious funds
- predicts cash-out
- initiates intervention
- selects **ALERT POLICE**

### Police

The same application then transitions to the Police context.

Police reviews:

- escalated case
- money trail
- predicted cash-out location
- terminal/geospatial evidence
- timeline
- audit information

Do not simulate two phones.

## Final A2 Story

### 1. Live Alert

A suspicious transaction enters the system.

CyberShield receives the alert live.

**Judge takeaway:** this is a real connected system, not a static UI.

### 2. Investigation

Open the incident.

Show:

- risk score
- explainable signals
- money trail
- relevant evidence

**Judge takeaway:** the system explains both *why* activity was flagged and *how* the money is moving.

### 3. Cash-Out Prediction

Show:

- predicted terminal
- ranked alternatives where available
- location
- time window
- supporting terminal/geospatial evidence

**Judge takeaway:** FraudLens predicts where the digital funds are likely to become physical cash.

### 4. Selective Fund Protection

Show the suspicious exposure being protected while legitimate balance remains unaffected where supported by the scenario.

Do not claim that arbitrary commingled funds can always be perfectly separated into individual rupees.

### 5. Withdrawal Attempt + Interception

**This must be included in the final A2 recording.**

Generate the withdrawal attempt and show:

- terminal
- amount
- timestamp
- status
- intervention/restriction

This is critical because cash-out interception is the project's core SIH differentiator.

### 6. Police Escalation

Bank Official selects:

**ALERT POLICE**

Then transition the same phone into the Police context.

Police reviews the structured case/dossier.

### 7. Audit / Final State

Show the relevant timeline/audit evidence and finish at a clear case state.

## Important A2 Correction

The rehearsal report's original five-scene recording sequence omitted the explicit **withdrawal attempt + interception** step.

The final A2 recording sequence must therefore be:

```text
LIVE ALERT
    ↓
INVESTIGATE
    ↓
MONEY TRAIL + RISK
    ↓
CASH-OUT PREDICTION
    ↓
SELECTIVE FUND PROTECTION
    ↓
WITHDRAWAL ATTEMPT
    ↓
WITHDRAWAL INTERCEPTION
    ↓
ALERT POLICE
    ↓
POLICE DOSSIER
    ↓
AUDIT / FINAL STATE
```

## What A2 Should NOT Show

Keep A2 narrative-focused.

Do not spend time on:

- Kafka throughput benchmarks
- bulk dataset generation
- raw mock API JSON
- deep synthetic identity-cluster inspection
- manual UDP/mDNS configuration
- implementation-level CLI details

Those belong in A1 only if they are visually useful.

## Jury Criteria

The rehearsal should support these eight SIH evaluation areas:

1. **Novelty** — the combination of connected money-trail intelligence with predictive cash-out terminal ranking.
2. **Clarity** — one coherent incident with an obvious causal progression.
3. **Feasibility** — real backend computation, graph processing, terminal ranking, and real mobile connectivity.
4. **Practicality** — bank investigation, fund protection, intervention, and police handoff.
5. **Sustainability** — modular, repeatable prototype architecture.
6. **Scale of Impact** — narrowing investigation from broad geography to likely physical cash-out locations.
7. **User Experience** — demonstrate genuine live backend → phone updates rather than static screens.
8. **Project Implementation** — visibly substantiate the major working modules without drowning the judge in implementation details.

Do not pretend that real bank-scale deployment, institutional APIs, legal authorization, or production infrastructure already exist. Those are production/future-extension points.

## A2 Final Recording Objective

The judge should finish the video understanding:

> A suspicious transaction is detected, its connected money movement is understood, the likely cash-out location is predicted, suspicious funds are protected, the withdrawal can be intercepted, and actionable intelligence can be escalated to law enforcement.

That is the operational story.

## Next Step

C is the completed rehearsal.

Next:

**A1 — Full Feature Walkthrough**

Then:

**A2 — Final Live Scenario Recording**

A1 answers:

> **What have they built?**

A2 answers:

> **How does it work in an actual incident?**
