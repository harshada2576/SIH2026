# CyberShield Prediction Validation Benchmark Report

**Document Status:** AUTOMATICALLY GENERATED FROM SEED RUNS  
**Evaluation Timestamp:** 2026-09-29T15:20:05.889221+00:00  
**Protocol Reference:** [`docs/VALIDATION_PROTOCOL.md`](file:///c:/Users/RAYED%20KHAN/Documents/Cash_Withdraw/SIH2026/docs/VALIDATION_PROTOCOL.md)  
**Synthetic Data Notice:** All metrics and scenarios are generated from synthetic data (`synthetic: true`).

---

## 1. Executive Summary & Verdict

- **Pre-Registered Verdict:** **SUCCESS: Predictor outperforms all baselines on Top-3 Hit Rate on held-out test data.**
- **Primary Metric (Top-3 Hit Rate, R=2.0 km):** **50.83% ± 2.58%**
- **95% Bootstrap Confidence Interval:** **[48.61%, 53.06%]**
- **Median Distance Error:** **449.05 km**

---

## 2. Model Performance vs Baselines

| Model / Baseline | Top-3 Hit Rate (Mean %) | Relative Lift vs Model |
|---|---|---|
| **CyberShield Predictor** | **50.83%** | **Ref** |
| Random Terminal Baseline | 10.00% | +408.34% |
| Most Frequent Historical Baseline | 46.11% | +10.25% |
| Nearest Centroid Baseline | 7.50% | +577.97% |

---

## 3. Score Reliability Table

| Priority Band | Total Count | Mean Priority | Empirical Top-3 Hit Rate |
|---|---|---|---|
| 0–30 (Low) | 0 | 0.0 | 0.0% |
| 30–60 (Medium) | 16 | 42.09 | 6.25% |
| 60–80 (High) | 37 | 74.82 | 56.76% |
| 80–100 (Critical) | 19 | 83.75 | 63.16% |

*Note: Table is labeled 'Score Reliability' as priority scores represent heuristic priority rankings, not calibrated probabilities.*

---

## 4. Multi-Seed Detailed Results

| Seed | Top-1 Hit Rate (%) | Top-3 Hit Rate (%) | Top-5 Hit Rate (%) | Median Dist Error (km) |
|---|---|---|---|---|
| Seed 42 | 36.11% | 47.22% | 47.22% | 529.01 km |
| Seed 43 | 37.50% | 52.78% | 56.94% | 201.35 km |
| Seed 44 | 37.50% | 48.61% | 51.39% | 514.86 km |
| Seed 45 | 37.50% | 54.17% | 56.94% | 491.00 km |
| Seed 46 | 37.50% | 51.39% | 52.78% | 509.02 km |
