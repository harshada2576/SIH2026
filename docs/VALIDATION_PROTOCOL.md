# CyberShield Hotspot Prediction Validation Protocol

**Document Status: PRE-REGISTERED (LOCKED)**  
**Version:** 1.0.0  
**Project:** CyberShield (SIH 2026, PS 26184, MHA/I4C)  

---

## 1. Executive Summary & Purpose
This document pre-registers the evaluation protocol for validating CyberShield's predictive cash-out hotspot interception engine against synthetic ground-truth withdrawal outcomes. To ensure objective, reproducible scientific evaluation, all metric definitions, baseline algorithms, difficulty tiers, dataset splits, seeds, and pre-registered success criteria are fixed in this document prior to performing final benchmark evaluations.

---

## 2. Definitions & Evaluation Criteria

### 2.1 Hit Definitions
- **Exact-Terminal Hit**: A prediction for a target account is counted as an exact hit if the predicted terminal ID strictly equals the actual ground-truth withdrawal terminal ID:
  $$\text{Hit}_{\text{exact}}(k) = \mathbb{I}\left( \exists \, i \in \{1, \dots, k\} : \text{predicted\_id}_i = \text{actual\_id} \right)$$
- **Radius Hit ($R = 2.0 \text{ km}$)**: A prediction is counted as a spatial radius hit if the actual ground-truth withdrawal location is within $R = 2.0\text{ km}$ of any of the top-$k$ predicted terminal locations, calculated using the Haversine formula:
  $$\text{Hit}_{\text{radius}}(k, R) = \mathbb{I}\left( \exists \, i \in \{1, \dots, k\} : \text{Haversine}(\text{pred\_lat}_i, \text{pred\_lon}_i, \text{act\_lat}, \text{act\_lon}) \le R \right)$$

### 2.2 Primary Metric
- **Top-3 Hit Rate (Radius $R = 2.0\text{ km}$)** on the held-out test set:
  $$\text{Top-3 Hit Rate} = \frac{1}{N_{\text{test}}} \sum_{j=1}^{N_{\text{test}}} \text{Hit}_{\text{radius}}^{(j)}(k=3, R=2.0\text{ km})$$

### 2.3 Secondary Metrics
1. **Top-1 Hit Rate**: Percentage of test scenarios where the rank-1 predicted terminal captures the actual cash-out location ($R \le 2.0\text{ km}$).
2. **Top-5 Hit Rate**: Percentage of test scenarios where any of the top-5 predicted terminals capture the actual cash-out location ($R \le 2.0\text{ km}$).
3. **Median Distance Error (km)**: Median spatial distance between the actual cash-out location and the highest-priority predicted terminal (Rank-1).
4. **Precision@K & Recall@K**: Precision and recall evaluated over candidate terminal sets.
5. **Time-Window Accuracy & Lead Time**:
   - *Lead Time (mins)*: Time difference between alert issuance and actual withdrawal attempt timestamp.
   - *Window Accuracy*: Percentage of actual withdrawal attempts falling strictly within the predicted window `[window_start, window_end]`.
6. **False-Positive Rate of High-Priority Predictions**: Rate of high-priority predictions (Priority $\ge 60$) that fail to fall within $R=2.0\text{ km}$ of the actual cash-out event.

---

## 3. Baselines & Lift Metrics
The CyberShield predictive heuristic engine will be benchmarked against three reference baselines:
1. **Random Terminal Baseline**: Selects $k$ candidate terminals uniformly at random from all active terminals in the dataset.
2. **Most Frequent Historical Terminal Baseline**: Selects candidate terminals based strictly on the target account's historical terminal usage frequency.
3. **Nearest Centroid Baseline**: Ranks terminals strictly by Euclidean / Haversine proximity to the target account's geographical operating centroid.

**Lift Calculation**:
$$\text{Lift}_{\text{baseline}} = \frac{\text{Metric}_{\text{CyberShield}} - \text{Metric}_{\text{baseline}}}{\text{Metric}_{\text{baseline}}} \times 100\%$$

---

## 4. Scenario Difficulty Tiers
Validation scenarios are classified into three mutually exclusive difficulty tiers to measure generalization under varying levels of behavioral obfuscation:

| Tier | Definition | Expected Mix Ratio |
|---|---|---|
| **EASY** | Actual cash-out terminal exists in the target account's historical terminal list. | 40% |
| **MEDIUM** | Actual terminal is NOT in history, but resides in the target account's primary district / within 10 km. | 40% |
| **HARD** | Actual terminal resides in a completely different district or involves cross-city layering hops. | 20% |

Metrics are reported overall and broken down across each difficulty tier.

---

## 5. Dataset Split Protocol
- **Time-Ordered Split**: To prevent temporal leakage, all scenarios are ordered chronologically by transaction timestamp.
- **70/30 Train/Test Split**:
  - First **70%** of scenarios constitute the historical observation graph (burn-in period).
  - Final **30%** of scenarios are reserved as the **held-out test evaluation set**.
- **Temporal Cutoff Guard**: The predictor function `rank_terminals(..., as_of=T)` and `GeoIntelligenceEngine` operate under a strict temporal boundary $T = t_{\text{trigger}}$, reading only transaction edges and metadata timestamped strictly before $T$.

---

## 6. Seed Configuration & Statistical Confidence
- Evaluation is executed across 5 fixed random seeds: `[42, 43, 44, 45, 46]`.
- For all metrics, results are reported as **Mean $\pm$ Standard Deviation**.
- A **95% Bootstrap Confidence Interval** (1,000 resamples) is calculated for the primary metric ($\text{Top-3 Hit Rate}$).

---

## 7. Pre-Registered Success Criteria
The CyberShield predictor will be declared **validated** if and only if:
1. **Primary Criterion**: CyberShield achieves a Top-3 Hit Rate ($R \le 2.0\text{ km}$) on the held-out test set that exceeds all three baseline models (Random, Most Frequent Historical, Nearest Centroid) overall and on the **MEDIUM** difficulty tier.
2. **Leakage Guard Criterion**: 100% pass rate on automated temporal leakage tests asserting no ground-truth access prior to evaluation.
3. **Determinism Criterion**: Running the evaluation harness twice with identical seed parameters yields 100% byte-identical validation reports.

Regardless of outcome, all empirical results will be recorded accurately in `data/output/validation_report.json` and `docs/VALIDATION_AND_INTEGRATION.md` without manual modification or post-hoc tuning.
