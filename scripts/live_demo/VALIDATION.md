# CyberShield Live Demo Validation & Test Suite Matrix (SIH26184)

**Total Scenarios**: 30  
**Pipeline**: Synthetic Transaction $\rightarrow$ Kafka `transactions` / POST `/transactions` $\rightarrow$ GraphStore $\rightarrow$ 11 Heuristic Explainable Rules $\rightarrow$ SQLite Persistence $\rightarrow$ WebSocket Broadcast $\rightarrow$ CyberShield Native Android App  
**Status**: **30 / 30 PASS (100% Pass Rate)**  
**Verification Date**: 2026-09-12  

---

## 📊 Summary by Set

| Set | Category | Scenario IDs | Scenarios Count | Result | Execution Time |
|---|---|---|---|---|---|
| **Set 1** | Core Heuristic Archetypes | `01` – `10` | 10 Scenarios | **10/10 PASS (100%)** | ~11.6s |
| **Set 2** | Advanced Fraud Scenarios | `11` – `20` | 10 Scenarios | **10/10 PASS (100%)** | ~11.1s |
| **Set 3** | Variants & Stress Scenarios | `21` – `30` | 10 Scenarios | **10/10 PASS (100%)** | ~11.5s |
| **Total** | **All Live Demo Scenarios** | `01` – `30` | **30 Scenarios** | **30/30 PASS (100%)** | **~34.6s** |

---

## 📋 Comprehensive 30-Scenario Validation Matrix

| # | Scenario File | Scenario Name & Archetype | Key Detection Rules Triggered | Target Terminal | Risk Score | Status |
|---|---|---|---|---|---|---|
| **01** | `01_simple_mule.py` | Simple Mule & Rapid Egress | `velocity`, `amount_movement`, `fan_in`, `account_age`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 55% | **PASS** |
| **02** | `02_layering.py` | Multi-Hop Layering Chain (4 hops) | `layering`, `velocity`, `amount_movement`, `identity_cluster` | `ATM-ICICI-Ce-004` | 50% | **PASS** |
| **03** | `03_fan_in.py` | Multi-Source Fan-In Consolidation | `fan_in` (5 sources), `velocity`, `amount_movement`, `terminal_affinity` | `AEPS-BCR-002` | 58% | **PASS** |
| **04** | `04_fan_out.py` | Rapid Multi-Destination Fan-Out | `fan_out` (4 destinations), `velocity`, `amount_movement`, `device_fingerprint` | `ATM-HDFC-Ce-001` | 54% | **PASS** |
| **05** | `05_rapid_forwarding.py` | Rapid Forwarding Velocity Spike | `velocity` (<2s gap), `amount_movement` (99%), `fan_in`, `ml_anomaly` | `ATM-HDFC-Ce-001` | 54% | **PASS** |
| **06** | `06_shared_device.py` | Shared Device Fingerprint Cluster | `device_fingerprint`, `velocity`, `amount_movement`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 55% | **PASS** |
| **07** | `07_multi_victim_common_mule.py` | Multi-Victim Common Mule Convergence | `fan_in` (4 regions), `velocity`, `amount_movement`, `terminal_affinity` | `AEPS-BCR-002` | 56% | **PASS** |
| **08** | `08_dormant_activation.py` | Dormant Account Reactivation | `velocity`, `amount_movement`, `fan_in`, `ml_anomaly` | `ATM-HDFC-Ce-001` | 52% | **PASS** |
| **09** | `09_repeated_atm_targeting.py` | Repeated ATM Terminal Targeting | `terminal_affinity`, `velocity`, `amount_movement`, `fan_in` | `ATM-HDFC-Ce-001` | 54% | **PASS** |
| **10** | `10_distributed_cashout.py` | Distributed Multi-Terminal Cashout | `fan_out`, `layering`, `velocity`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 58% | **PASS** |
| **11** | `11_cross_city_mule.py` | Cross-City Mule Migration | `velocity`, `amount_movement`, `fan_in`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 55% | **PASS** |
| **12** | `12_probing_then_large.py` | Micro-Probing Followed by Rapid Burst | `velocity`, `amount_movement`, `fan_in`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 55% | **PASS** |
| **13** | `13_geo_velocity.py` | Impossible Geo-Velocity Anomaly | `velocity`, `amount_movement`, `fan_in`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 55% | **PASS** |
| **14** | `14_fan_in_fan_out.py` | Concentrator Fan-In / Fan-Out Hub | `fan_in` (5 sources), `fan_out` (4 targets), `velocity`, `amount_movement` | `AEPS-BCR-002` | 58% | **PASS** |
| **15** | `15_shared_kyc_cluster.py` | Shared KYC Identity Syndicate | `identity_cluster`, `fan_in`, `velocity`, `amount_movement` | `ATM-HDFC-Ce-001` | 51% | **PASS** |
| **16** | `16_concurrent_campaign.py` | Concurrent Dual-Campaign Blitz | `velocity`, `amount_movement`, `fan_in`, `terminal_affinity` | `AEPS-BCR-002` | 55% | **PASS** |
| **17** | `17_amount_escalation.py` | Progressive Amount Escalation Ladder | `velocity`, `amount_movement`, `fan_in`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 54% | **PASS** |
| **18** | `18_rapid_multi_account_cashout.py` | Coordinated Multi-Account Cashout Sweep | `velocity`, `amount_movement`, `fan_in`, `terminal_affinity` | `AEPS-BCR-002` | 54% | **PASS** |
| **19** | `19_cross_device_mule_chain.py` | Hardware Fingerprint Syndicate Chain | `device_fingerprint`, `velocity`, `amount_movement`, `fan_in` | `ATM-HDFC-Ce-001` | 59% | **PASS** |
| **20** | `20_layering_with_distributed_cashout.py` | Layering with Distributed Cashout Split | `layering`, `fan_out`, `velocity`, `amount_movement` | `ATM-HDFC-Ce-001` | 50% | **PASS** |
| **21** | `21_simple_mule_variant.py` | High-Value Simple Mule Variant | `velocity`, `amount_movement`, `fan_in`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 55% | **PASS** |
| **22** | `22_layering_variant.py` | Deep 5-Hop Layering Chain Variant | `layering` (5 hops), `velocity`, `amount_movement`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 50% | **PASS** |
| **23** | `23_fan_in_variant.py` | High-Frequency Fan-In Avalanche | `fan_in` (6 sources), `velocity`, `amount_movement`, `terminal_affinity` | `AEPS-BCR-002` | 58% | **PASS** |
| **24** | `24_fan_out_variant.py` | High-Velocity Fan-Out Split Variant | `fan_out` (5 targets), `velocity`, `amount_movement`, `fan_in` | `ATM-HDFC-Ce-001` | 55% | **PASS** |
| **25** | `25_rapid_forwarding_variant.py` | Ultra-Rapid Forwarding Variant | `velocity` (<1s gap), `amount_movement` (99.8%), `fan_in`, `terminal_affinity` | `ATM-HDFC-Ce-001` | 54% | **PASS** |
| **26** | `26_shared_device_variant.py` | Shared Hardware Cluster Variant | `device_fingerprint`, `velocity`, `amount_movement`, `fan_in` | `ATM-HDFC-Ce-001` | 59% | **PASS** |
| **27** | `27_multi_victim_variant.py` | Multi-Victim Scam Feeder Variant | `fan_in` (5 victims), `velocity`, `amount_movement`, `terminal_affinity` | `AEPS-BCR-002` | 56% | **PASS** |
| **28** | `28_dormant_activation_variant.py` | Long-Dormant Reactivation Variant | `velocity`, `amount_movement`, `fan_in` (5 sources), `terminal_affinity` | `ATM-HDFC-Ce-001` | 52% | **PASS** |
| **29** | `29_repeated_terminal_variant.py` | Concentrated ATM Corridor Sweep Variant | `terminal_affinity`, `velocity`, `amount_movement`, `fan_in` | `ATM-HDFC-Ce-001` | 54% | **PASS** |
| **30** | `30_distributed_cashout_variant.py` | 4-Way Multi-Terminal Cashout Variant | `fan_out` (4 targets), `fan_in` (4 sources), `velocity`, `amount_movement` | `AEPS-BCR-002` | 58% | **PASS** |

---

## 🛠️ Verification Commands

```bash
# Run all 30 live demo scenarios
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --all

# Run by specific set
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --set 1
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --set 2
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --set 3

# Dry-run test (simulation mode)
PYTHONPATH=. .venv/bin/python scripts/live_demo/run_all_live_demos.py --dry-run
```
