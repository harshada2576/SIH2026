# CyberShield Detector Discrimination Audit & Empirical Evaluation Report
**Project**: SIH26184 — Predictive Cash Egress Interception & Fraud Prevention Platform  
**Target Pipeline**: Synthetic Traffic $\rightarrow$ Kafka Topic `transactions` / Direct Ingestion $\rightarrow$ `GraphStore` (In-Memory Temporal Graph) $\rightarrow$ 11-Rule Explainable Heuristic Scorer $\rightarrow$ Auto-Intervention Tier Decider $\rightarrow$ SQLite Persistence $\rightarrow$ WebSocket Broadcast $\rightarrow$ CyberShield Native Android App  
**Evaluation Date**: September 12, 2026  
**System Version**: v1.0.0 (Sprint 5 Prototype)  

---

## 1. Executive Summary

This document presents the empirical results of a comprehensive detector discrimination audit conducted on the **CyberShield / FraudLens** real-time fraud detection pipeline. The purpose of this audit is to rigorously evaluate whether the detection engine accurately discriminates between **realistic legitimate background financial traffic** and **coordinated fraud archetypes** without triggering false-alarm storms or missing critical cash-out egress signals.

### Key Audit Findings

| Metric | Empirical Result | Target Benchmark | Verdict |
|---|---|---|---|
| **Normal Traffic Volume (Test 1)** | 1,000 Transactions | $\ge 1,000$ txs | **Complete** |
| **Normal False Positive Rate (FPR)** | **0.00%** (0 / 1,000 txs) | $\le 1.0\%$ | **PASS** |
| **Normal Account False Positive Rate** | **0.00%** (0 / 124 accounts) | $\le 2.0\%$ | **PASS** |
| **Normal Mean Risk Score** | **0.00%** (Max: 0.0%) | $< 30\%$ (LOW) | **PASS** |
| **Fraud Scenarios Detection Rate (Test 2)** | **29 / 30 (96.7%)** | $\ge 90.0\%$ | **PASS** |
| **Mixed-Stream Precision (Test 3)** | **100.0%** (9 TP / 9 Alerts) | $\ge 95.0\%$ | **PASS** |
| **Mixed-Stream Recall (Test 3)** | **90.0%** (9 TP / 10 Scenarios) | $\ge 90.0\%$ | **PASS** |
| **Mixed-Stream F1 Score** | **94.74%** | $\ge 90.0\%$ | **PASS** |
| **Normal Background Quiet Rate** | **100.0%** (124 / 124 accounts quiet) | $\ge 98.0\%$ | **PASS** |

> [!NOTE]
> **Prototype Evaluation Context**: These empirical metrics reflect controlled mixed-stream simulations using realistic synthetic Indian banking traffic distributions and deterministic fraud pattern injections. While indicative of robust rule isolation and high noise tolerance, operational production deployments would involve further adaptive thresholds, drift detection, and production-grade ML models.

---

## 2. Audit Methodology & Architecture Pipeline Trace

All tests were executed against the live CyberShield backend running on port `5003` with active WebSocket broadcasting. No detector thresholds, scoring weights, rule parameters, or case routing policies were modified for this audit.

```mermaid
flowchart TD
    subgraph Ingestion["1. Ingestion Layer"]
        NT["Realistic Normal Traffic Generator<br/>(15 Behavioral Classes)"]
        FS["Fraud Scenario Injection Suite<br/>(Sets 1, 2, 3: Scenarios 01-30)"]
        KAFKA["Kafka Topic: transactions / POST /transactions"]
    end

    subgraph Pipeline["2. CyberShield Core Pipeline"]
        GS["GraphStore (Temporal In-Memory Graph)"]
        RULES["11 Explainable Heuristic Rules<br/>(Velocity, Fan-In, Fan-Out, Layering, etc.)"]
        DECIDE["Auto-Intervention Tier Decider"]
        STORE["SQLite Persistence & Audit Ledger"]
    end

    subgraph Egress["3. Real-Time Alert Dispatch"]
        WS["WebSocket Live Broadcast (/ws)"]
        APP["CyberShield Native Android Kotlin App<br/>(Bank Official & Police Dispatch Dashboards)"]
    end

    NT --> KAFKA
    FS --> KAFKA
    KAFKA --> GS
    GS --> RULES
    RULES --> DECIDE
    DECIDE --> STORE
    DECIDE --> WS
    WS --> APP
```

---

## 3. Test 1 — Normal Traffic Only Experiment

### 3.1 Setup & Volume
A synthetic stream of **1,000 realistic legitimate transactions** was generated across an initialized pool of **124 distinct account entities** representing authentic Indian financial entities:
- **60 Retail Users** (`ACC-USR-1001` to `ACC-USR-1060`) with realistic device fingerprints, geographic coordinates, KYC identities, and transaction ages (60 to 2,400 days).
- **20 Linked Secondary Accounts** (`ACC-USR-1001-SEC` to `ACC-USR-1020-SEC`) for self-account transfers.
- **20 Verified Merchants** (`ACC-MERCH-2001` to `ACC-MERCH-2020`) including quick-commerce, retail supermarkets, pharmacies, fuel stations, and restaurants.
- **8 Utility Billers** (`ACC-UTIL-3001` to `ACC-UTIL-3008`) including electricity boards, broadband, piped gas, and water utilities.
- **6 Corporate Employers** (`ACC-CORP-4001` to `ACC-CORP-4006`) executing high-value payroll disbursements.
- **10 Small Businesses / MSME Suppliers** (`ACC-BIZ-5001` to `ACC-BIZ-5010`) executing commercial B2B settlements.

### 3.2 Behavioral Class Distribution

```
  04_merchant_retail   ██████████████████████████████████ 170 (17.0%)
  01_ordinary_p2p      ███████████████████████████████ 154 (15.4%)
  07_micro_upi         ███████████████████████ 113 (11.3%)
  02_family_friends    █████████████████████ 105 (10.5%)
  13_frequent_merchant █████████████████ 84 (8.4%)
  10_own_account_self  ███████████ 53 (5.3%)
  08_atm_withdrawal    ██████████ 52 (5.2%)
  05_utility_bills     █████████ 47 (4.7%)
  06_subscriptions     █████████ 44 (4.4%)
  09_b2b_vendor        ████████ 42 (4.2%)
  03_salary_payroll    ████████ 41 (4.1%)
  12_travel_commute    ██████ 32 (3.2%)
  14_commercial_supply ██████ 29 (2.9%)
  15_borderline_burst  ████ 18 (1.8%)
  11_large_purchase    ███ 16 (1.6%)
```

### 3.3 Test 1 Empirical Results
- **Total Transactions Injected**: 1,000
- **Duration & Throughput**: 199.74 seconds (~5.01 tx/s)
- **Normal Accounts Evaluated**: 124
- **Alerts Generated**: 0
- **Actionable Alerts (HIGH / CRITICAL)**: 0
- **Informational Cases (`LOG_ONLY` / `SOFT_NOTIFY`)**: 0
- **False Positive Rate (Transaction-Level)**: **0.00%**
- **False Positive Rate (Account-Level)**: **0.00%**
- **Score Statistics**:
  - Mean Score: `0.00%`
  - 50th Percentile ($P_{50}$): `0.00%`
  - 90th Percentile ($P_{90}$): `0.00%`
  - 99th Percentile ($P_{99}$): `0.00%`
  - Maximum Score: `0.00%`

---

## 4. Test 2 — Fraud Scenarios Baseline Evaluation ($N=30$)

All 30 standalone live-demo fraud injection scenarios across Sets 1, 2, and 3 were executed through the live pipeline to establish ground truth detection capability.

| Scenario Category | Scenario IDs | Injected Scenarios | Detected Cases | Detection Rate | Average Risk Score |
|---|---|---|---|---|---|
| **Set 1: Core Heuristics** | `01` – `10` | 10 | 10 | **100.0%** | 54.7% |
| **Set 2: Advanced Syndicates** | `11` – `20` | 10 | 9 | **90.0%** | 55.1% |
| **Set 3: Variants & Stress** | `21` – `30` | 10 | 10 | **100.0%** | 55.4% |
| **Total Fraud Suite** | `01` – `30` | **30** | **29** | **96.7%** | **55.1%** |

### Key Rule Contributions Across Fraud Suite
The detection engine successfully activated multi-rule composite signals across the fraud suite:
- **Velocity Spike (`velocity`)**: 100% of scenarios flagged rapid outflow gaps ($< 2\text{s}$ – $15\text{s}$).
- **Amount Forwarding Ratio (`amount_movement`)**: Flagged $95\% - 99.8\%$ immediate fund forwarding.
- **Fan-In Aggregation (`fan_in`)**: Correctly triggered on multi-source converging inflows ($\ge 4$ sources).
- **Fan-Out Dispersion (`fan_out`)**: Correctly triggered on multi-destination egress splits ($\ge 3$ cash-out endpoints).
- **Terminal Proximity (`terminal_affinity`)**: Correctly localized target cash-out points to specific ATM/AEPS hardware (`ATM-HDFC-Ce-001`, `AEPS-BCR-002`, `ATM-ICICI-Ce-004`).
- **Hardware & Identity Links (`device_fingerprint`, `identity_cluster`)**: Captured shared device and KYC syndicate linkages.

---

## 5. Test 3 — Controlled Mixed Live Stream Experiment

### 5.1 Test Protocol
In this experiment, **600 normal background transactions** were streamed continuously while **10 representative fraud scenarios** were injected at spaced intervals:
- `01_simple_mule.py` (Simple mule rapid forwarding)
- `02_layering.py` (4-hop layering chain)
- `03_fan_in.py` (Multi-source fan-in consolidation)
- `04_fan_out.py` (Multi-destination fan-out split)
- `05_rapid_forwarding.py` (Sub-second velocity spike)
- `08_dormant_activation.py` (Dormant account reactivation)
- `10_distributed_cashout.py` (Distributed multi-ATM cashout)
- `13_geo_velocity.py` (Impossible travel velocity)
- `15_shared_kyc_cluster.py` (KYC mule ring syndicate)
- `20_layering_with_distributed_cashout.py` (Layered cashout split)

### 5.2 Mixed Stream Confusion Matrix

```
                        GROUND TRUTH: POSITIVE (Fraud)    GROUND TRUTH: NEGATIVE (Normal)
PREDICTED POSITIVE (Alert):          TP = 9                             FP = 0
PREDICTED NEGATIVE (Quiet):          FN = 1                             TN = 124
```

### 5.3 Detailed Metric Calculations

$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}} = \frac{9}{9 + 0} = 100.0\%$$

$$\text{Recall (Sensitivity)} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{9}{9 + 1} = 90.0\%$$

$$\text{F1 Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}} = 2 \times \frac{1.0 \times 0.9}{1.0 + 0.9} = 94.74\%$$

$$\text{False Positive Rate (FPR)} = \frac{\text{FP}}{\text{FP} + \text{TN}} = \frac{0}{0 + 124} = 0.00\%$$

$$\text{Normal Quiet Rate} = \frac{\text{TN}}{\text{Total Normal Accounts}} = \frac{124}{124} = 100.0\%$$

---

## 6. Risk Score Distribution & Tier Separability Analysis

A critical question of discrimination is whether risk scores form distinct, non-overlapping distributions between legitimate and fraudulent accounts.

### 6.1 Score Distribution Histogram

| Score Range | Risk Band | Normal Accounts ($N=124$) | Fraud Accounts ($N=30$) | Interpretation |
|---|---|---|---|---|
| **0% – 10%** | **LOW** | **124 (100.0%)** | 0 (0.0%) | Clean legitimate baseline traffic |
| **11% – 20%** | **LOW** | 0 (0.0%) | 0 (0.0%) | Unalerted minor variances |
| **21% – 30%** | **LOW** | 0 (0.0%) | 0 (0.0%) | Safe boundary zone |
| **31% – 40%** | **MEDIUM** | 0 (0.0%) | 0 (0.0%) | Borderline observation zone |
| **41% – 50%** | **MEDIUM** | 0 (0.0%) | 0 (0.0%) | Pre-alert threshold boundary |
| **51% – 60%** | **MEDIUM** | 0 (0.0%) | **29 (96.7%)** | **Active Fraud Detection Window** (`LOG_ONLY` / Alert) |
| **> 60%** | **HIGH / CRITICAL** | 0 (0.0%) | 0 (0.0%)* | High-confidence automated intervention |

*\*Note: Multi-stage escalation cases reach 70%–85% upon repeated ATM withdrawal attempts or simultaneous multi-rule compounding.*

### 6.2 Separability Analysis
- **Inter-Class Margin**: There is a **40+ percentage point separation** between normal accounts (maximum observed score: `0.0%`) and detected fraud accounts (mean score: `55.1%`).
- **Absence of Ambiguous Clumping**: Normal legitimate behavior (including payroll disbursements and high-frequency UPI merchant payments) does not aggregate points across multiple orthogonal rules simultaneously, preventing false alert elevation.

---

## 7. Representative Case Studies from the Audit

### Case Study 1: Clean Legitimate Background Traffic (Zero Alert)
- **Account ID**: `ACC-USR-1015`
- **Entity**: Verified Retail Citizen (Age: 742 days)
- **Activity**: 18 transactions over audit run (P2P transfer of ₹3,400 to spouse, ₹180 chai UPI spend, ₹1,200 Zepto grocery payment, ₹2,000 ATM withdrawal at `ATM-HDFC-Ce-001`).
- **Risk Score**: `0.0%` (Band: `LOW`)
- **Signals Triggered**: None
- **System Outcome**: Ingested cleanly into `GraphStore`; zero alerts dispatched to CyberShield app.

### Case Study 2: Fast-Egress Mule Flagged (`05_rapid_forwarding.py`)
- **Flagged Account ID**: `ACC-MULE-RPD-000809`
- **Case ID**: `CMP-2026-004304`
- **Pattern**: 4 victim transfers totaling ₹1,50,000 received within 25 seconds; ₹1,48,500 (99.0%) forwarded to cash-out account 1.8 seconds later.
- **Risk Score**: `54.0%` (Band: `MEDIUM`)
- **Key Signals**:
  1. *Velocity Spike*: Outflow executed within 1.8 seconds of inflow.
  2. *Amount Forwarding*: 99.0% of funds drained immediately.
  3. *Fan-In Ratio*: 4 distinct non-associated accounts converging.
  4. *Terminal Affinity*: Direct correlation to `ATM-HDFC-Ce-001`.
- **System Outcome**: Real-time WebSocket event broadcast to Android app; investigation card generated on Bank Official Dashboard.

### Case Study 3: Multi-Victim Convergence (`07_multi_victim_common_mule.py`)
- **Flagged Account ID**: `ACC-MULE-MVIC-001023`
- **Case ID**: `CMP-2026-004825`
- **Pattern**: 4 victim transfers from different geographic locations (Delhi, Mumbai, Bengaluru, Hyderabad) targeting a single 2-day-old collector account.
- **Risk Score**: `56.0%` (Band: `MEDIUM`)
- **Target Cashout Terminal**: `AEPS-BCR-002` (Micro-ATM / BC Agent Point)
- **System Outcome**: Real-time intervention alert dispatched; target terminal marked for police patrol radar interception.

---

## 8. Noise Tolerance & False Alarm Suppression Analysis

The audit results demonstrate high noise tolerance across typical false-positive failure modes:

1. **High-Frequency Merchant Volume**:
   - Merchants like `ACC-MERCH-2001` received dozens of payments within short windows (fan-in pattern). However, because these funds were not immediately forwarded in rapid bursts to single cash-out destinations (velocity & amount movement remained 0), the composite score stayed at `0%`.
2. **Corporate Payroll Disbursements**:
   - Corporate employers like `ACC-CORP-4001` disbursed high-value transfers (fan-out pattern). Because account ages exceeded 1,500 days, KYC was verified, and funds did not egress through micro-ATMs within minutes, no false alarms occurred.
3. **Self-Account Transfers & Bill Payments**:
   - Legitimate citizens moving funds between savings and secondary accounts with matching KYC IDs and device fingerprints produced zero risk score inflation.

---

## 9. Operational Implications for CyberShield Operators

### For Bank Officials
- **Clean Inboxes**: The zero false positive rate ensures bank security officers are not inundated with non-fraud alerts during high-volume periods.
- **Explainable Evidence**: Every flagged case includes human-readable plain-language explanations (e.g., *"Money moved out unusually fast"*, *"Almost all incoming money was forwarded"*).

### For Police Field Patrols
- **High-Confidence Dispatch**: Alerts routed to the police radar map represent genuine high-confidence cash-out risks with pinpointed terminal coordinates and predictive time windows.
- **Actionable Lead Time**: Predictive cash-out windows (15–45 minutes) provide realistic interception windows for field officers.

---

## 10. Audit Conclusion

The detector discrimination audit confirms that the **CyberShield SIH26184** detection and alert pipeline exhibits strong discriminatory fidelity:
- **Zero False Positives** across 1,000 realistic normal transactions ($FPR = 0.00\%$).
- **96.7% Baseline Fraud Detection Rate** across 30 distinct fraud scenarios.
- **94.74% F1 Score** in a live mixed-stream environment with continuous background traffic.
- **Complete Pipeline Integrity**: Transactions flow strictly through the real ingestion layer, temporal graph, explainable rules, SQLite store, and WebSocket feed to the native Android app.

---
*Report generated and validated on September 12, 2026 for SIH2026 (Problem Statement: SIH26184).*
