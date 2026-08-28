# Rules.md — Guardrails for AI-Assisted Building

Everyone is using AI tools to build their piece. These rules exist so 6 people's AI sessions don't each reinvent the stack differently. When prompting your AI tool, paste the relevant section of `Architecture.md` first so it builds to the contract, not to whatever it defaults to.

## Stack rules
- **Python only.** No mixing in Node/Java/Go for any workstream piece, even if your AI suggests it's "better for streaming" — consistency across 3 pairs matters more than marginal tech fit this week.
- **Stick to the libraries named in Architecture.md**: `kafka-python`/`confluent-kafka`, `networkx`, `FastAPI`, Leaflet.js via CDN. If your AI tool suggests adding a new major dependency (a different graph DB, a different web framework, a message queue alternative), stop and ask the group first — don't just accept it because the AI suggested it.
- **No real ML/GNN training.** Detection = explainable rules/heuristics (fan-in/fan-out counting, time-window thresholds, device fingerprint matching), not a trained model. If your AI tool starts scaffolding PyTorch/GNN training code, redirect it — that's future-work, not this week's build.
- **Dataset size**: aim for low thousands to tens of thousands of synthetic transactions — enough to visibly demonstrate scale in a live demo, not gigabytes. If generation is taking more than a few minutes to run locally, it's too big for our timeline.

## Data & schema rules
- **Never deviate from the 4 JSON schemas in Architecture.md** without posting the change in the group chat. This is the single most important rule — schema drift is what breaks integration on Sept 1.
- No real names, real account numbers, or any real PII in synthetic data — all identifiers should be obviously synthetic (e.g., `ACC-00042`).

## Error handling / robustness expectations
- Each workstream should fail loudly and locally (clear error message, doesn't crash the whole pipeline) rather than silently dropping events.
- It's fine if error handling is minimal/rough for a prototype — don't let your AI tool over-engineer retry logic, circuit breakers, or production-grade resilience. That's time you don't have this week.

## What AI tools should NOT do on this project
- Don't add authentication/login systems — not needed for a local demo.
- Don't add a database beyond what's needed (no Postgres/MongoDB setup — the in-memory graph + Kafka is enough).
- Don't "polish" scope beyond what Architecture.md defines — if your AI tool suggests extra features (user roles, historical analytics dashboards, export-to-PDF reports), politely decline unless the group agrees it's worth the time.
- Don't silently rename JSON fields for "clarity" — even a well-intentioned rename breaks the contract for the other 2 workstreams.

## Communication rule
- Any change to Architecture.md's schemas, topic names, or tech stack gets posted in the group chat before you build against it — not after.
- If you're blocked waiting on another workstream's output, say so immediately rather than mocking around it silently for a day — mocked stand-ins are fine short-term, just flag it so integration doesn't surprise anyone on Sept 1.
