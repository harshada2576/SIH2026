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

---

### 5. Essential Commands & Demo Catalog

| Task | Command | Description |
| :--- | :--- | :--- |
| **Start Full Server Hub** | `.venv/bin/python3 scripts/run_hackathon.py` | Starts Mock Bank (8001), Mock NCRP (8002), and CyberShield API (5003). |
| **Run Tamper Demo** | `.venv/bin/python3 -m audit.tamper_demo` | Proves blockchain immutability, disk tampering detection, and O(log N) SMT proof verification. |
| **Run E2E Replay Flow** | `.venv/bin/python3 scripts/verify_e2e_flow.py` | Validates streaming ingestion, 8 rules + ML, SQLite persistence, and Section 63 BSA dossier export. |
| **Run Mule Ring & Geo-Velocity** | `.venv/bin/python3 scripts/demo_phase2.py` | Demonstrates a 12-mule shared KYC identity cluster + Mumbai-to-Hyderabad "impossible travel" alert. |
| **Run Full Case Orchestration** | `.venv/bin/python3 scripts/demo_full_case_orchestration.py` | Runs the full 11-step lifecycle: Detection -> Hold -> Police Dispatch -> Resolution. |
| **Run Police Alert Workflow** | `.venv/bin/python3 scripts/demo_police_alert_workflow.py` | Shows Bank-to-Police alert dispatch, data minimization, and live state synchronization. |
| **Run Notification System** | `.venv/bin/python3 scripts/demo_notification_system.py` | Demonstrates real-time multi-channel notifications (SMS + HTML Email) with de-duplication. |
| **Run Full Test Suite** | `.venv/bin/pytest tests/ -v` | Runs all **166 automated unit & integration tests** across the entire stack. |

---

### 6. 4-Slide Pitch Outline

1. **Slide 1: Problem Context & The Proactive Paradigm Shift**
   * The 8,000+ daily complaints bottleneck; why reactive post-cashout liens fail; pre-egress dual-track intervention.
2. **Slide 2: System Architecture & Alignment with PS 26184 Key Deliverables**
   * Analytics Engine (Rules + ML) + GIS Radar + Android Native App + Multi-Channel Notification Hub.
3. **Slide 3: Cybersecurity, Blockchain & Section 63 BSA Legal Admissibility**
   * Sparse Merkle Tree (SMT) O(log N) inclusion proofs, Ed25519 block signing, and statutory electronic evidence certificates.
4. **Slide 4: Technical Scalability, Feasibility & Real-World Impact**
   * Kafka cluster graph synchronization, 10,000+ TPS capacity, Redis Pub/Sub, and 166 verified automated tests.

---

### 7. Video Demonstration Storyboard & Pitch Guide

#### 🎬 Recommended Video Duration: 3 to 5 Minutes

#### **Scene 1: The Problem Hook (0:00 – 0:45)**
* **Visual:** Visual representation of money hopping rapidly across mule accounts and cash withdrawn before a victim even dials NCRP 1930.
* **Narration:** Explain the fundamental challenge: *"Today, India's cybercrime defense is reactive. Mules withdraw cash at ATMs within 30 minutes, long before a victim dials 1930. CyberShield solves this by predicting the cashout point and intervening before the cash leaves the machine."*

#### **Scene 2: Backend Pipeline & Heuristics in Action (0:45 – 1:45)**
* **Visual:** Terminal screen showing `.venv/bin/python3 scripts/demo_phase2.py` or `.venv/bin/python3 scripts/run_hackathon.py` ingesting high-velocity transactions, detecting a 12-mule ring and impossible travel geo-velocity.
* **Narration:** Highlight the hybrid detection engine: *"CyberShield uses 8 explainable heuristics—including structured smurfing, shared KYC rings, and geo-velocity—paired with Isolation Forest ML anomaly scoring and sub-millisecond graph traversal."*

#### **Scene 3: The Android Native App & Real-Time Alert (1:45 – 3:00)**
* **Visual:** Screen recording of the CyberShield Android Kotlin App (or running on a physical phone/emulator).
  * **Radar Map Tab:** Show the cash-out radar map with predicted ATMs, confidence circles, and risk levels.
  * **Cases Queue Tab:** Open a critical case (`NCRP-CASE-...`).
  * **Dual-Action Protocol:** Show the **Bank Official** placing a *Selective Hold* (preserving untouched funds) and clicking **"Send to Police"**.
  * **Police View:** Switch role to **Police Investigator**, show the incident packet, target ATM coordinates, and navigation route.

#### **Scene 4: Blockchain Trust, Section 63 BSA Dossier & Tamper Demo (3:00 – 4:15)**
* **Visual:** Show the **Evidentiary Dossier Card** in the Android app with its green `IMMUTABLE` badge and Section 63 BSA certificate.
* **Visual:** Run `.venv/bin/python3 -m audit.tamper_demo` in terminal, showing the Merkle tree inclusion proof verifying in milliseconds and instantly catching disk-level risk score tampering.
* **Narration:** *"Under the new Bharatiya Sakshya Adhiniyam, 2023, digital evidence must be tamper-evident. CyberShield anchors every action in an Ed25519-signed Sparse Merkle Tree, generating O(log N) inclusion proofs for instant judicial verification."*

#### **Scene 5: Summary & Impact (4:15 – 5:00)**
* **Visual:** Summary slide showing key stats: 166 automated test cases, 25,000+ accounts benchmark, sub-second graph traversal.
* **Narration:** *"CyberShield provides I4C and law enforcement with a proactive, high-throughput, and legally unassailable weapon against cyber fraud."*

---

### 8. Artifact & Binary Locations
* **Debug APK:** `CyberShield/app/build/outputs/apk/debug/app-debug.apk`
* **Core API:** `api/server.py`
* **Merkle Ledger:** `audit/merkle_ledger.py`
* **Section 63 BSA Dossier:** `export/evidentiary_dossier.py`
* **Cluster Graph Store:** `pipeline/cluster_graph.py`
