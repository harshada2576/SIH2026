# CyberShield (SIH 2026 - Problem Statement ID 26184)
## Predictive Analytics Framework for Cybercrime Complaints & Proactive Cash Withdrawal Interception

---

### Executive Summary
* **Problem Statement ID:** 26184
* **Organization:** Ministry of Home Affairs (MHA)
* **Department:** Indian Cyber Crime Coordination Centre (I4C), CIS Division
* **Category / Theme:** Software / Blockchain & Cybersecurity
* **Core Mission:** Transition national cybercrime intervention from **post-incident reactive reporting** (NCRP 1930) to **pre-egress real-time predictive interception** within the critical 15–30 minute cash-out window.

---

### 1. The Core Problem & Our Solution

#### The Ground Reality & Bottleneck
* The National Cybercrime Reporting Portal (NCRP) receives **8,000+ complaints daily**, with financial cyber fraud causing thousands of crores in illicit fund egress annually.
* **The Traditional Flaw:** Current workflows are *reactive*. By the time a victim notices fraud and dials 1930 to request a bank lien, the illicit funds have already hopped across 3–5 intermediate mule accounts and been withdrawn as physical cash at an ATM or AEPS Micro-ATM.

#### The CyberShield Proactive Paradigm
CyberShield ingests real-time high-velocity transaction streams across UPI, IMPS, NEFT, and AEPS. By applying causal multi-hop graph traversal, explainable heuristics, and unsupervised anomaly detection, it forecasts the physical cash-out corridor and triggers a **dual-track intervention**:
1. **Bank Official Track:** Automated *provisional hold* on the incoming suspicious funds delta (e.g. ₹100,000), preserving the customer's existing legitimate balance (e.g. ₹20,000) to eliminate wrongful customer harassment.
2. **Police / LEA Track:** Predicts the exact ATM / AEPS terminal candidate and dispatches actionable intelligence with geospatial coordinates to the nearest field patrol unit *before* cash dispensing occurs.

---

### 2. Frontend Architecture Mandate

> **MANDATE:** The **ONLY frontend** for this project is the **CyberShield Native Android Kotlin App** (`CyberShield/`), built with Kotlin & Jetpack Compose.
> There is **NO web dashboard or JavaScript frontend**.
>
> **Why Native Android?**
> * Field police investigators and bank duty officers operate in mobile and transit environments.
> * Native Android provides zero-config local hotspot UDP/mDNS discovery, real-time WebSocket alert broadcasting, and local offline resilience.

---

### 3. End-to-End System Architecture

```mermaid
flowchart TD
    subgraph Data & Streaming Ingestion
        A["National Banking Streams (UPI / IMPS / AEPS)"] --> B["Kafka Ingestion Topic ('transactions')"]
        B --> C["ClusterGraphStore (Partition Convergence)"]
    end

    subgraph Detection & Predictive Analytics Engine
        C --> D["Hybrid Scorer Engine"]
        D --> E1["8 Heuristic Detection Rules"]
        D --> E2["Isolation Forest ML Anomaly Scoring"]
        D --> E3["Spatial Terminal Ranking & Corridor Decay"]
    end

    subgraph Blockchain, Trust & Legal Admissibility
        E1 & E2 & E3 --> F["Sparse Merkle Tree (SMT) Ledger"]
        F --> G["Ed25519 Block Signing & Tamper Defense"]
        F --> H["Section 63 BSA / 65B IEA Evidentiary Dossier"]
    end

    subgraph Dispatch & Mobile App
        D --> I["Decoupled Redis/Async EventBus"]
        I --> J["WebSocket Alert Broadcaster"]
        J --> K["CyberShield Native Android Kotlin App"]
    end
```

---

### 4. Detailed Pillar Breakdown

#### Pillar 1: Cybersecurity, Blockchain & Legal Admissibility
* **Sparse Merkle Tree (SMT) Immutable Ledger (`audit/merkle_ledger.py`):**
  * Every transaction, risk score, and officer intervention is committed into a cryptographic Merkle Block.
  * Produces **O(log N) sibling-path inclusion proofs (`MerkleAuditProof`)**—enabling instant, standalone verification of case integrity in court without scanning the full blockchain history.
  * Block roots are digitally signed using **Ed25519 keypairs** with automated disk-tampering detection.
* **Section 63 BSA, 2023 / Section 65B IEA Evidentiary Dossier (`export/evidentiary_dossier.py`):**
  * Automatically exports court-admissible electronic evidence certificates containing canonical SHA-256 digests, chronological hop leg hashes, and Merkle root anchoring for LEA charge-sheeting.
* **Zero-Trust Security & Anti-Replay (`api/security.py`):**
  * HMAC-SHA256 request signing, sliding ±300s timestamp windows, and bounded nonce caches to protect bank freezing and police dispatch APIs against replay and MITM attacks.

#### Pillar 2: High-Velocity Kafka & Cluster Graph Ingestion
* **`ClusterGraphStore` (`pipeline/cluster_graph.py`):**
  * Solves the **Kafka multi-hop partition fragmentation paradox** (e.g., Hop 1 on Partition 1, Hop 2 on Partition 2) through thread-safe atomic batch synchronization and sub-millisecond BFS causal trail recovery.

#### Pillar 3: Multi-Worker Pub/Sub & Engine Scaling
* **Decoupled `EventBus` (`api/pubsub.py`):**
  * Multi-worker Uvicorn clustering with Redis Pub/Sub for cross-worker WebSocket synchronization, with automated zero-config in-memory fallback for standalone/offline demos.
* **FastAPI Server (`api/server.py`):**
  * Serves REST endpoints for cases, terminals, heatmaps, and Section 63 BSA dossiers (`GET /cases/{id}/dossier`) alongside dynamic LAN UDP discovery.

#### Pillar 4: Prediction Validation & Institutional Adapters
* **Pre-Registered Prediction Validation (`docs/VALIDATION_PROTOCOL.md` & `engine/validation_engine.py`):**
  * Evaluated across 70/30 time-ordered split under strict temporal cutoff (`as_of`) guards to eliminate data leakage.
  * Achieves **51.39% ± 2.50% Top-3 Hit Rate** (within 2.0 km radius) with 95% Bootstrap CI `[47.22%, 54.17%]`, representing a **+145.2% relative lift** over random baseline.
* **Institutional Integration Layer (`pipeline/integration_adapters.py`):**
  * Role-specific connectors for **Bank CBS** (differential provisional hold), **Police LEA** (patrol dispatch packet), and **I4C NCRP** (threat indexing).
  * Strict human-in-the-loop review guard with mandatory justification logging into the cryptographic audit ledger.

---

### 5. Essential Commands & Demo Catalog

| Task | Command | Description |
| :--- | :--- | :--- |
| **Start Full Server Hub** | `.venv/bin/python3 scripts/run_hackathon.py` | Starts Mock Bank (8001), Mock NCRP (8002), and CyberShield API (5003). |
| **Run Tamper Demo** | `.venv/bin/python3 -m audit.tamper_demo` | Proves blockchain immutability, disk tampering detection, and O(log N) SMT proof verification. |
| **Run E2E Replay Flow** | `.venv/bin/python3 scripts/verify_e2e_flow.py` | Validates streaming ingestion, 16 rules + ML, SQLite persistence, and Section 63 BSA dossier export. |
| **Run Mule Ring & Geo-Velocity** | `.venv/bin/python3 scripts/demo_phase2.py` | Demonstrates a 12-mule shared KYC identity cluster + Mumbai-to-Hyderabad "impossible travel" alert. |
| **Run Full Case Orchestration** | `.venv/bin/python3 scripts/demo_full_case_orchestration.py` | Runs the full 11-step lifecycle: Detection -> Hold -> Police Dispatch -> Resolution. |
| **Run Police Alert Workflow** | `.venv/bin/python3 scripts/demo_police_alert_workflow.py` | Shows Bank-to-Police alert dispatch, data minimization, and live state synchronization. |
| **Run Prediction Benchmark** | `.venv/bin/python3 -m engine.validation_engine` | Executes pre-registered multi-seed validation benchmark across difficulty tiers. |
| **Run Full Test Suite** | `.venv/bin/pytest tests/ -v` | Runs all **177 automated unit & integration tests** across the entire stack (100% pass). |

---

### 6. Live Deployments & Distribution

| Layer | Environment | URL / Endpoint | Verification |
| :--- | :--- | :--- | :--- |
| **Evaluator Portal** | GitHub Pages (Actions) | [https://harshada2576.github.io/SIH2026/](https://harshada2576.github.io/SIH2026/) | Interactive API explorer & live status |
| **Cloud Production API** | Render / Custom CNAME | [https://cybershield-backend-g8fl.onrender.com](https://cybershield-backend-g8fl.onrender.com) / [https://sih-render.seucra.tech](https://sih-render.seucra.tech) | Root & Health 200 OK telemetry |
| **Signed Release APK** | GitHub Releases (`v0.0.1`) | [https://github.com/harshada2576/SIH2026/releases/tag/v0.0.1](https://github.com/harshada2576/SIH2026/releases/tag/v0.0.1) | APK Signature Scheme v2 (I4C Keystore) |

---

### 7. 4-Slide Pitch Outline

1. **Slide 1: Problem Context & The Proactive Paradigm Shift**
   * The 8,000+ daily complaints bottleneck; why reactive post-cashout liens fail; pre-egress dual-track intervention.
2. **Slide 2: System Architecture & Alignment with PS 26184 Key Deliverables**
   * Analytics Engine (Rules + ML) + GIS Radar + Android Native App + Multi-Channel Notification Hub.
3. **Slide 3: Cybersecurity, Blockchain & Section 63 BSA Legal Admissibility**
   * Sparse Merkle Tree (SMT) O(log N) inclusion proofs, Ed25519 block signing, and statutory electronic evidence certificates.
4. **Slide 4: Technical Scalability, Validation Benchmarks & Real-World Impact**
   * Kafka cluster graph synchronization, 10,000+ TPS capacity, +145% predictor lift, and 177 verified automated tests.

---

### 8. Artifact & Binary Locations
* **Signed Release APK:** `release_apk/CyberShield-v1.0.0-release.apk` (52.01 MiB, SHA-256: `91cd2833e004e0758b1a33dbb11889b4f8b544294946a696be2b4c17f563a5cb`)
* **I4C Keystore:** `CyberShield/cybershield-release.jks` (RSA 2048-bit, 10,000 days validity)
* **Core API:** `api/server.py`
* **Merkle Ledger:** `audit/merkle_ledger.py`
* **Section 63 BSA Dossier:** `export/evidentiary_dossier.py`
* **Cluster Graph Store:** `pipeline/cluster_graph.py`
* **Validation Report:** `data/output/validation_report.json`

---

### 9. Core Engineering Team & Attribution

| Contributor | GitHub Handle | Key Architectural Responsibilities |
| :--- | :--- | :--- |
| **seucra** | [`@seucra`](https://github.com/seucra) | Architecture, Full-Stack Systems, Merkle Ledger & Section 63 BSA Engine |
| **Harshada Avhad** | [`@harshada2576`](https://github.com/harshada2576) | Team Lead, ML Systems, Hybrid Scoring & Geospatial Intelligence |
| **Shreya Nikam** | [`@NikamShreya696`](https://github.com/NikamShreya696) | Data Engineering, 1 Crore Synthetic Generator & Macro Trend Modeling |
| **The-CoDexR3kt** | [`@The-CoDexR3kt`](https://github.com/The-CoDexR3kt) | Backend Infrastructure, Kafka Streams & Fast Storage Persistence |
| **Abaan Mhaisker** | [`@abaanmhaisker`](https://github.com/abaanmhaisker) | Security Architecture, Cryptography & Prediction Validation Engine |
| **Dakshata Mhatre** | [`@DakshataMhatre`](https://github.com/DakshataMhatre) | Mobile Engineering, Jetpack Compose Radar Map & Tactical UI/UX |

---

### 10. Licensing & Legal Governance

This software is licensed under the **Apache License, Version 2.0** (`LICENSE`).
* **Explicit Patent Grant (Section 3):** Protects deploying LEAs, banks, and users from third-party patent assertion.
* **Statutory Alignment:** Fully compliant with Digital Personal Data Protection (DPDP) Act, 2023 and Section 63 of Bharatiya Sakshya Adhiniyam (BSA), 2023.
