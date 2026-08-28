# Design.md — Visual Direction for the Dashboard
### SIH26184 — Predictive Cash Egress Interception
**Status: EDITABLE / loose. Functionality and the scalability demo matter far more than visual polish. Fill in or override anything here.**

---

## Why this file is short on purpose
A judge is evaluating whether you understand the problem and have a technically sound, working pipeline — not whether your CSS is beautiful. Spend minutes here, not hours. That said, a genuinely unreadable or cluttered dashboard actively hurts you in a live demo, so a few concrete defaults below are worth just adopting rather than debating from scratch.

## Suggested wireframe (ASCII, redraw however you like)

```
┌──────────────────────────────────────────────────────────────────┐
│  [Team/Project Name]     Predictive Cash Egress Interception       │
├───────────────────────────────────────────┬────────────────────────┤
│                                             │  ALERT FEED             │
│                                             │  ─────────────────      │
│                                             │  ● CMP-2026-000451       │
│                                             │    risk: 0.91 (HIGH)    │
│           [ LEAFLET MAP ]                  │    ACC-00891             │
│    - terminal markers, color = risk        │    → ATM-SBI-ND-042      │
│    - clicking a marker highlights           │    window: 10:30-11:15  │
│      its alert in the side panel            │  ─────────────────      │
│                                             │  ● CMP-2026-000452       │
│                                             │    risk: 0.62 (MED)     │
│                                             │  ─────────────────      │
│                                             │                          │
├───────────────────────────────────────────┴────────────────────────┤
│  EVIDENCE PANEL (for selected alert)                                │
│  • Shares device fingerprint with known mule cluster                │
│  • Fan-in of 5 accounts within 3 minutes                             │
│  • Historical cash-out affinity: this terminal, 0.83 similarity      │
└──────────────────────────────────────────────────────────────────┘
```

## Layout principles
- **Map-first**: the map is the visual centerpiece — it's the thing that makes this look like a real system rather than a spreadsheet. Everything else supports it.
- **Alert feed as a live list**, most recent/highest-risk at top — this is what you'll be narrating during the live demo ("watch this alert appear as the fraud pattern completes").
- **Evidence panel updates on click** — this is your explainability story made visible. Don't skip this even if time is short; it's one of the most convincing parts of the demo because it directly answers "how do you know this is fraud, not just a rule triggering randomly."

## Color coding (suggested, change freely)
| Risk level | Score range | Color |
|---|---|---|
| Low | < 0.4 | Green |
| Medium | 0.4 - 0.7 | Yellow/Amber |
| High | > 0.7 | Red |

Use this consistently on both the map markers and the alert feed — a judge should be able to glance at the screen and immediately understand severity without reading text.

## Presentation-room legibility (non-negotiable, unlike the color choices)
- Large fonts throughout — assume your laptop screen is being projected and the back row needs to read alert text.
- High contrast — don't rely on subtle color differences; risk levels should be obviously distinguishable even on a mediocre projector.
- Minimal clutter — no unnecessary chrome, animations, or decorative elements competing with the map and alert feed for attention.
- Test the actual projector/screen-share setup before your slot if at all possible — colors and contrast often look different than on your laptop.

## Not decided yet / genuinely up to whoever builds it
- Exact color palette beyond the green/yellow/red risk scale
- Font choices (a clean system font is completely fine — don't spend time here)
- Whether to add team name/branding treatment
- Whether the alert feed auto-scrolls/highlights new entries, or is manually refreshed

*(Genuinely fine to leave most of this file's open questions unresolved and just make reasonable choices while building. This exists so there's a place to record decisions as you make them, not to gate anyone's work before they start.)*
