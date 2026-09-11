# CyberShield — Frontend Rework (Sept 2026)

## What was actually broken

The app ran fine, but the core investigator workflow described in the plan —
**view all suspicious cases → open one → review its evidence → approve/hold/
dismiss → move to the next one** — didn't exist. Specifically:

1. **Every case looked the same.** `InvestigationScreen` always rendered
   `MockDataRepository.complaintTickets.first()`, hardcoded. Tapping *any*
   case in the queue, or *any* marker on the map, opened the exact same
   NCRP-994821 case every time. There was no way to inspect a specific case.
2. **Status was global, not per-case.** `investigationStatus` was a single
   variable in the ViewModel. Approving one case would have changed the
   status shown for every case, because there was only ever one status.
3. **Evidence/money-trail data was global too.** `primaryMoneyTrail` and
   `primaryRiskBreakdown` existed once, not per-case — so even if you *could*
   open a different case, it would show the wrong evidence.
4. **Heavy unexplained jargon in the client UI**: "XAI Score Breakdown",
   "CBS Hold via CFCFRMS", "Topology / Fan-In Signal", "Spatial ATM Affinity".
   None of this is something a police officer using the app needs to parse
   to make a decision.
5. **No real queue.** The old "Dispatch Center" screen showed a *pending
   review* list, but selecting an item still fell into bug #1 above — it
   never actually opened that item.

## What changed

**Data layer** (`model/Models.kt`, `data/MockDataRepository.kt`)
Every `ComplaintTicket` is now fully self-contained: its own `moneyTrail`,
`riskBreakdown`, and a new plain-English `summary` field. 5 distinct,
realistic cases instead of 1 real case + 4 empty shells.

**State layer** (`MainViewModel.kt`)
`cases` is now a live, mutable list — the single source of truth. Every
action (`approveAndForward`, `issueBankHold`, `dismissFalsePositive`) takes
an explicit `ncrpId` and updates *only* that case. `caseById()` and
`caseForTerminal()` let any screen look up the right case.

**Navigation** (`ui/navigation/NavGraph.kt`)
Added a real `case_detail/{ncrpId}` route. Opening a case is a genuine
navigation to that case's data, not a tab switch to a fixed screen.

**Screens** — restructured around the actual workflow instead of a fixed
3-tab "Radar / Investigation / Dispatch" layout that didn't reflect how the
app is used:

| Before | After | Why |
|---|---|---|
| Cashout Radar (map) | **Map** | same idea, terminal count bug fixed, tapping a case marker now opens *that* case |
| Investigation (always showed 1 case) | **Cases** (queue, default tab) | shows every case, filterable (Needs Review / All / Resolved), tap any card to inspect it |
| Dispatch Center (queue + audit mixed) | **Activity** (pure audit log) | accountability trail only — queue moved to Cases where it belongs |
| — | **Case Detail** (pushed screen, not a tab) | full one-by-one review: plain-language summary, evidence, money trail, Send to Police / Freeze Account / Dismiss |

**Plain-language pass** — every screen a police officer actually reads now
leads with plain English:
- "IN PLAIN TERMS: ₹50 lakh moved through 6 accounts in under 4 minutes..."
  instead of a raw risk score with no context.
- Each evidence signal is a full sentence ("Money moved out unusually fast")
  with a "Show technical details" toggle for officers who want the
  underlying rule name (`velocity_rule`, `geo_velocity_rule`, etc.) — hidden
  by default, never the primary label.
- "Freeze Account (Bank Hold)" instead of "Issue CBS Hold via CFCFRMS".
- "Send to Police" instead of "Approve & Forward".

## The fixed flow

```
Cases tab (default landing screen)
   │
   ├─ Summary cards: Awaiting Review / Sent to Police / Accounts Frozen
   ├─ Filter: Needs Review / All Cases / Resolved
   │
   ▼ tap any case
Case Detail (pushed screen, back arrow)
   │
   ├─ Plain-language headline
   ├─ Case details (amount, predicted location, time window)
   ├─ How the money moved (trail diagram)
   ├─ Why this was flagged (plain-language evidence, technical detail optional)
   │
   ▼ pick one
Send to Police / Freeze Account / Dismiss
   │
   ▼ confirm
Back to Cases — that case now shows its new status, case count updates,
action recorded in Activity
```

Map markers behave the same way: tap a marker → "Review the Linked Case" →
opens that specific case's detail, not a fixed example.
