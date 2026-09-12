# CyberShield Live Demo Suite & Background Traffic Stream (SIH26184)

This suite provides both **Realistic Normal Background Traffic Generation** and **30 Standalone Live Fraud Scenario Injections** designed for live hackathon demonstrations of **CyberShield / FraudLens**.

All traffic (both normal background flow and fraud injections) streams through the **REAL production pipeline**:
$$\text{Live Transactions} \rightarrow \text{Kafka topic 'transactions'} \rightarrow \text{Consumer Daemon} \rightarrow \text{GraphStore} \rightarrow \text{11-Rule Detection Scorer} \rightarrow \text{SQLite} \rightarrow \text{WebSocket Broadcast} \rightarrow \text{CyberShield Android App}$$

---

## 🚦 Live Demonstration Workflow (Recommended for Judges)

During a live demo or presentation, you can run continuous background traffic (at ~2–3× the volume of fraud injections) while selectively triggering fraud scenarios. This visually proves that the system handles ordinary banking traffic quietly while instantly intercepting malicious money mules.

```
┌────────────────────────────────────────────────────────┐
│ 1. Terminal 1: Start Normal Background Traffic         │
│    python scripts/live_demo/normal_traffic.py          │
│    --continuous --rate 5                               │
└──────────────────────────┬─────────────────────────────┘
                           │ (Continuous normal transactions)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 2. Terminal 2: Inject Live Fraud Scenarios             │
│    python scripts/live_demo/run_all_live_demos.py      │
│    --set 1                                             │
└──────────────────────────┬─────────────────────────────┘
                           │ (Real-time detection & alerts)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 3. CyberShield Android Device:                         │
│    - Ordinary transactions update the money graph      │
│    - Fraud scenario raises immediate NEW_ALERT toast   │
│    - Risk radar map prioritizes target cashout ATM     │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start Commands

### 1. Normal Background Traffic Generator

#### Foreground Stream (Interactive Display)
```bash
# Continuous realistic stream at 5 transactions/second
PYTHONPATH=. .venv/bin/python scripts/live_demo/normal_traffic.py --continuous --rate 5

# Run for fixed duration (e.g. 5 minutes = 300s)
PYTHONPATH=. .venv/bin/python scripts/live_demo/normal_traffic.py --duration 300 --rate 5

# High volume stress stream (15 tx/s)
PYTHONPATH=. .venv/bin/python scripts/live_demo/normal_traffic.py --continuous --rate 15
```
*To stop the foreground generator cleanly at any time, press `Ctrl+C`.*

#### Background Daemon Mode (`run_background.py`)
```bash
# Start background generator
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_background.py start --rate 5

# Check status
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_background.py status

# Monitor live log output
tail -f data/output/normal_traffic.log

# Stop cleanly
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_background.py stop
```

---

### 2. Live Fraud Injection Scenarios

```bash
# Run all 30 live fraud scenarios sequentially (~35s)
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --all

# Run specific scenario sets:
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --set 1   # Core Archetypes (01-10)
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --set 2   # Advanced Fraud (11-20)
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --set 3   # Variants & Stress (21-30)

# Run any single scenario standalone:
PYTHONPATH=. .venv/bin/python scripts/live_demo/01_simple_mule.py
PYTHONPATH=. .venv/bin/python scripts/live_demo/02_layering.py
PYTHONPATH=. .venv/bin/python scripts/live_demo/14_fan_in_fan_out.py
```

---

## 🧠 15 Legitimate Behavioral Classes

The normal traffic generator generates non-fraudulent transactions spanning 15 realistic Indian financial classes:

| # | Behavioral Class | Typical Amount (INR) | Channels | Characteristics |
|---|---|---|---|---|
| **01** | **Ordinary P2P** | ₹100 – ₹8,000 | UPI, IMPS | Peer-to-peer transfers between retail users. |
| **02** | **Family & Friends** | ₹1,000 – ₹25,000 | UPI, IMPS | Regular transfers between linked family contacts. |
| **03** | **Salary & Corporate Payroll** | ₹35,000 – ₹1,75,000 | NEFT, RTGS | Monthly corporate disbursements to employees. |
| **04** | **Merchant Retail** | ₹50 – ₹8,500 | UPI, POS | Supermarket, grocery, pharmacy, food delivery payments. |
| **05** | **Utility & Bill Payments** | ₹250 – ₹4,800 | UPI | Power (BESCOM/Tata), telecom (Airtel/Jio), gas, water. |
| **06** | **Recurring Subscriptions** | ₹199 – ₹1,499 | UPI | OTT, SaaS, gym, media subscriptions. |
| **07** | **Micro-UPI Transactions** | ₹10 – ₹240 | UPI | Street food, chai, auto-rickshaw fares, small conveniences. |
| **08** | **Normal ATM Cash Withdrawals** | ₹500 – ₹10,000 | AEPS | Cash withdrawal at user's designated local ATM terminal. |
| **09** | **Small Business B2B Invoices** | ₹15,000 – ₹1,20,000 | NEFT, IMPS | Commercial settlements between suppliers & retailers. |
| **10** | **Self / Own-Account Transfers** | ₹2,000 – ₹45,000 | IMPS | Transfers between user's Savings & Secondary accounts. |
| **11** | **Large Legitimate Purchases** | ₹60,000 – ₹2,20,000 | NEFT | Vehicle deposit, tuition fee, electronics purchase. |
| **12** | **Travel & Commute** | ₹850 – ₹14,500 | UPI | Metro card recharge, flight/train tickets, hotel stays. |
| **13** | **Frequent / Favorite Merchant** | ₹120 – ₹950 | UPI | Daily coffee, bakery, or regular neighborhood kirana. |
| **14** | **Commercial Supply Chain** | ₹25,000 – ₹85,000 | NEFT | Wholesale merchant stock replenishments. |
| **15** | **Borderline Festive Rush** | ₹1,500 – ₹18,000 | UPI | Seasonal shopping spikes (non-mule, legitimate spend). |

---

## 📋 Comprehensive Live Fraud Scenarios (30 Scenarios)

### Set 1: Core Heuristics (`01` – `10`)
* **01 (`01_simple_mule.py`)**: Simple Mule & Rapid Egress (₹1.5L, <8s forward)
* **02 (`02_layering.py`)**: Multi-Hop Layering Chain (Victim $\rightarrow$ M1 $\rightarrow$ M2 $\rightarrow$ M3 $\rightarrow$ Aggr)
* **03 (`03_fan_in.py`)**: Multi-Source Fan-In Consolidation (5 feeder accounts)
* **04 (`04_fan_out.py`)**: Rapid Multi-Destination Fan-Out (4 target mules)
* **05 (`05_rapid_forwarding.py`)**: High-Frequency Velocity Spike (99% forward in <3s)
* **06 (`06_shared_device.py`)**: Shared Device Fingerprint Cluster (Hardware IMEI ring)
* **07 (`07_multi_victim_common_mule.py`)**: Multi-Victim Cross-City Nexus Mule (4 cities)
* **08 (`08_dormant_activation.py`)**: Sudden Dormant Account Reactivation (365-day dormant)
* **09 (`09_repeated_atm_targeting.py`)**: Repeated ATM Terminal Targeting (ATM-HDFC-Ce-001)
* **10 (`10_distributed_cashout.py`)**: Multi-Terminal Distributed Cashout (3 ATM/AEPS nodes)

### Set 2: Advanced Fraud (`11` – `20`)
* **11 (`11_cross_city_mule.py`)**: Cross-City Mule Migration (BLR $\rightarrow$ CHN $\rightarrow$ MUM $\rightarrow$ DEL)
* **12 (`12_probing_then_large.py`)**: Micro-Probing Followed by Rapid Large-Scale Burst
* **13 (`13_geo_velocity.py`)**: Impossible Geo-Velocity Anomaly (Distant city terminals)
* **14 (`14_fan_in_fan_out.py`)**: Concentrator Fan-In / Fan-Out Clearing Hub
* **15 (`15_shared_kyc_cluster.py`)**: Shared Synthetic KYC Identity Syndicate
* **16 (`16_concurrent_campaign.py`)**: Concurrent Dual-Campaign Phishing Blitz
* **17 (`17_amount_escalation.py`)**: Progressive Amount Escalation Ladder
* **18 (`18_rapid_multi_account_cashout.py`)**: Coordinated Multi-Account ATM Cashout Sweep
* **19 (`19_cross_device_mule_chain.py`)**: Hardware Fingerprint Syndicate Chain (5 nodes)
* **20 (`20_layering_with_distributed_cashout.py`)**: Layering Chain with Distributed Cashout Split

### Set 3: Variants & Stress (`21` – `30`)
* **21 (`21_simple_mule_variant.py`)**: High-Value Simple Mule Variant (₹2.4L turnover)
* **22 (`22_layering_variant.py`)**: Deep 5-Hop Layering Chain Variant
* **23 (`23_fan_in_variant.py`)**: High-Frequency Fan-In Avalanche (6 victim feeds)
* **24 (`24_fan_out_variant.py`)**: High-Velocity Fan-Out Split Variant (5-way split)
* **25 (`25_rapid_forwarding_variant.py`)**: Ultra-Rapid Forwarding Variant (<1s pass-through)
* **26 (`26_shared_device_variant.py`)**: Shared Rooted Handset Cluster Variant
* **27 (`27_multi_victim_variant.py`)**: Multi-Victim Scam Feeder Variant (5 urgent victims)
* **28 (`28_dormant_activation_variant.py`)**: Long-Dormant Reactivation Variant (450 days dormant)
* **29 (`29_repeated_terminal_variant.py`)**: Concentrated ATM Corridor Sweep Variant
* **30 (`30_distributed_cashout_variant.py`)**: 4-Way Multi-Terminal Cashout Variant
