#!/usr/bin/env python3
"""
scripts/run_validation.py — Benchmark Hotspot Predictor across multi-seed runs
Executes validation protocol, computes mean +/- std, bootstrap CIs, lift vs baselines,
verifies determinism, and outputs validation_report.json & validation_report.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "data-generator") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "data-generator"))

from normal_traffic import generate_accounts, generate_terminals, generate_normal_transactions
from patterns import inject_all_scenarios
from pipeline.validation_engine import run_single_seed_validation, calculate_bootstrap_ci


def parse_args():
    p = argparse.ArgumentParser(description="Run CyberShield Hotspot Validation Protocol across seeds.")
    p.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44, 45, 46])
    p.add_argument("--out-dir", type=str, default=str(REPO_ROOT / "data" / "output"))
    p.add_argument("--num-accounts", type=int, default=300)
    p.add_argument("--num-terminals", type=int, default=40)
    p.add_argument("--normal-txns", type=int, default=500)
    return p.parse_args()


def generate_seed_dataset(seed: int, num_acc: int, num_term: int, num_norm: int):
    """Generate synthetic dataset for a specific seed."""
    rng = random.Random(seed)
    accounts = generate_accounts(num_acc, rng)
    terminals = generate_terminals(num_term, rng)
    sim_start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    normal_txns = generate_normal_transactions(accounts, num_norm, rng)
    fraud_txns, scenarios = inject_all_scenarios(accounts, terminals, sim_start, rng)
    all_txns = normal_txns + fraud_txns
    return accounts, terminals, all_txns, scenarios


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running CyberShield Prediction Validation across seeds {args.seeds}...")

    seed_results = []
    for seed in args.seeds:
        accounts, terminals, all_txns, scenarios = generate_seed_dataset(seed, args.num_accounts, args.num_terminals, args.normal_txns)
        res = run_single_seed_validation(scenarios, accounts, terminals, all_txns, seed=seed)
        seed_results.append(res)
        print(f"  - Seed {seed}: Top-3 Hit Rate = {res['overall']['top3_radius']:.2f}%, Median Error = {res['overall']['median_distance_km']:.2f} km")

    # Aggregate across seeds
    top3_rates = [r['overall']['top3_radius'] for r in seed_results]
    top1_rates = [r['overall']['top1_radius'] for r in seed_results]
    med_dists = [r['overall']['median_distance_km'] for r in seed_results]

    mean_top3 = sum(top3_rates) / float(len(top3_rates))
    std_top3 = (sum((x - mean_top3)**2 for x in top3_rates) / float(len(top3_rates)))**0.5

    mean_top1 = sum(top1_rates) / float(len(top1_rates))
    mean_dist = sum(med_dists) / float(len(med_dists))

    ci_low, ci_high = calculate_bootstrap_ci(top3_rates, seed=42)

    avg_b_rand = sum(r['baselines']['random_top3'] for r in seed_results) / float(len(seed_results))
    avg_b_hist = sum(r['baselines']['history_top3'] for r in seed_results) / float(len(seed_results))
    avg_b_cent = sum(r['baselines']['centroid_top3'] for r in seed_results) / float(len(seed_results))

    lift_vs_rand = round(((mean_top3 - avg_b_rand) / avg_b_rand * 100) if avg_b_rand > 0 else 0.0, 2)
    lift_vs_hist = round(((mean_top3 - avg_b_hist) / avg_b_hist * 100) if avg_b_hist > 0 else 0.0, 2)
    lift_vs_cent = round(((mean_top3 - avg_b_cent) / avg_b_cent * 100) if avg_b_cent > 0 else 0.0, 2)

    # Pre-registered criteria verdict
    verdict_passed = mean_top3 > max(avg_b_rand, avg_b_hist, avg_b_cent)
    verdict_str = "SUCCESS: Predictor outperforms all baselines on Top-3 Hit Rate on held-out test data." if verdict_passed else "FAIL: Predictor did not exceed baseline thresholds."

    summary = {
        "synthetic": True,
        "pre_registered_protocol": "docs/VALIDATION_PROTOCOL.md",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seeds_evaluated": args.seeds,
        "aggregate_metrics": {
            "top3_hit_rate_mean_pct": round(mean_top3, 2),
            "top3_hit_rate_std_pct": round(std_top3, 2),
            "top1_hit_rate_mean_pct": round(mean_top1, 2),
            "median_distance_error_km": round(mean_dist, 2),
            "bootstrap_ci_95": {"low": round(ci_low, 2), "high": round(ci_high, 2)},
        },
        "baselines_mean_top3_pct": {
            "random": round(avg_b_rand, 2),
            "history": round(avg_b_hist, 2),
            "centroid": round(avg_b_cent, 2),
        },
        "lift_percent": {
            "vs_random": lift_vs_rand,
            "vs_history": lift_vs_hist,
            "vs_centroid": lift_vs_cent,
        },
        "pre_registered_verdict": verdict_str,
        "seed_runs": seed_results,
    }

    # Write JSON report
    json_path = out_dir / "validation_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Write Markdown report
    md_content = f"""# CyberShield Prediction Validation Benchmark Report

**Document Status:** AUTOMATICALLY GENERATED FROM SEED RUNS  
**Evaluation Timestamp:** {summary['timestamp']}  
**Protocol Reference:** [`docs/VALIDATION_PROTOCOL.md`](file:///c:/Users/RAYED%20KHAN/Documents/Cash_Withdraw/SIH2026/docs/VALIDATION_PROTOCOL.md)  
**Synthetic Data Notice:** All metrics and scenarios are generated from synthetic data (`synthetic: true`).

---

## 1. Executive Summary & Verdict

- **Pre-Registered Verdict:** **{verdict_str}**
- **Primary Metric (Top-3 Hit Rate, R=2.0 km):** **{mean_top3:.2f}% ± {std_top3:.2f}%**
- **95% Bootstrap Confidence Interval:** **[{ci_low:.2f}%, {ci_high:.2f}%]**
- **Median Distance Error:** **{mean_dist:.2f} km**

---

## 2. Model Performance vs Baselines

| Model / Baseline | Top-3 Hit Rate (Mean %) | Relative Lift vs Model |
|---|---|---|
| **CyberShield Predictor** | **{mean_top3:.2f}%** | **Ref** |
| Random Terminal Baseline | {avg_b_rand:.2f}% | +{lift_vs_rand:.2f}% |
| Most Frequent Historical Baseline | {avg_b_hist:.2f}% | +{lift_vs_hist:.2f}% |
| Nearest Centroid Baseline | {avg_b_cent:.2f}% | +{lift_vs_cent:.2f}% |

---

## 3. Score Reliability Table

| Priority Band | Total Count | Mean Priority | Empirical Top-3 Hit Rate |
|---|---|---|---|
| 0–30 (Low) | {seed_results[0]['score_reliability_table'][0]['count']} | {seed_results[0]['score_reliability_table'][0]['mean_priority']} | {seed_results[0]['score_reliability_table'][0]['empirical_top3_hit_rate']}% |
| 30–60 (Medium) | {seed_results[0]['score_reliability_table'][1]['count']} | {seed_results[0]['score_reliability_table'][1]['mean_priority']} | {seed_results[0]['score_reliability_table'][1]['empirical_top3_hit_rate']}% |
| 60–80 (High) | {seed_results[0]['score_reliability_table'][2]['count']} | {seed_results[0]['score_reliability_table'][2]['mean_priority']} | {seed_results[0]['score_reliability_table'][2]['empirical_top3_hit_rate']}% |
| 80–100 (Critical) | {seed_results[0]['score_reliability_table'][3]['count']} | {seed_results[0]['score_reliability_table'][3]['mean_priority']} | {seed_results[0]['score_reliability_table'][3]['empirical_top3_hit_rate']}% |

*Note: Table is labeled 'Score Reliability' as priority scores represent heuristic priority rankings, not calibrated probabilities.*

---

## 4. Multi-Seed Detailed Results

| Seed | Top-1 Hit Rate (%) | Top-3 Hit Rate (%) | Top-5 Hit Rate (%) | Median Dist Error (km) |
|---|---|---|---|---|
"""
    for r in seed_results:
        md_content += f"| Seed {r['seed']} | {r['overall']['top1_radius']:.2f}% | {r['overall']['top3_radius']:.2f}% | {r['overall']['top5_radius']:.2f}% | {r['overall']['median_distance_km']:.2f} km |\n"

    md_path = REPO_ROOT / "data" / "output" / "validation_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\nValidation complete. Reports written to:\n  - {json_path}\n  - {md_path}")


if __name__ == "__main__":
    main()
