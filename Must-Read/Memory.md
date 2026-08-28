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

*(No entries yet — first person to sit down and build starts this. One block per session, most recent at the bottom or top — pick one convention as a team and stick to it.)*
