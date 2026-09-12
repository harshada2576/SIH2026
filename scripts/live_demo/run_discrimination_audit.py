#!/usr/bin/env python3
"""
scripts/live_demo/run_discrimination_audit.py — Comprehensive Detector Discrimination Audit Harness
SIH26184 — Predictive Cash Egress Interception

Executes:
- Test 1: Normal Traffic Only (>= 1,000 legitimate transactions)
- Test 2: Fraud Scenarios Baseline (30 standalone live fraud scenarios)
- Test 3: Mixed Live Stream (Interleaved continuous background + fraud scenarios)
- Statistical & Confusion Matrix Computation
- Outputs machine-readable results JSON for DISCRIMINATION_AUDIT.md generation
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import math
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.kafka_utils import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRANSACTIONS_TOPIC,
    get_kafka_producer,
)
from scripts.live_demo.common import (
    DEFAULT_API_URL,
    _http_get_json,
    _http_post_json,
    get_now_utc,
    format_iso,
)
from scripts.live_demo.normal_traffic import AccountPool, NormalTrafficGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("discrimination_audit")

FRAUD_MODULES = [
    ("01", "01_simple_mule", "01_simple_mule.py"),
    ("02", "02_layering", "02_layering.py"),
    ("03", "03_fan_in", "03_fan_in.py"),
    ("04", "04_fan_out", "04_fan_out.py"),
    ("05", "05_rapid_forwarding", "05_rapid_forwarding.py"),
    ("06", "06_shared_device", "06_shared_device.py"),
    ("07", "07_multi_victim_common_mule", "07_multi_victim_common_mule.py"),
    ("08", "08_dormant_activation", "08_dormant_activation.py"),
    ("09", "09_repeated_atm_targeting", "09_repeated_atm_targeting.py"),
    ("10", "10_distributed_cashout", "10_distributed_cashout.py"),
    ("11", "11_cross_city_mule", "11_cross_city_mule.py"),
    ("12", "12_probing_then_large", "12_probing_then_large.py"),
    ("13", "13_geo_velocity", "13_geo_velocity.py"),
    ("14", "14_fan_in_fan_out", "14_fan_in_fan_out.py"),
    ("15", "15_shared_kyc_cluster", "15_shared_kyc_cluster.py"),
    ("16", "16_concurrent_campaign", "16_concurrent_campaign.py"),
    ("17", "17_amount_escalation", "17_amount_escalation.py"),
    ("18", "18_rapid_multi_account_cashout", "18_rapid_multi_account_cashout.py"),
    ("19", "19_cross_device_mule_chain", "19_cross_device_mule_chain.py"),
    ("20", "20_layering_with_distributed_cashout", "20_layering_with_distributed_cashout.py"),
    ("21", "21_simple_mule_variant", "21_simple_mule_variant.py"),
    ("22", "22_layering_variant", "22_layering_variant.py"),
    ("23", "23_fan_in_variant", "23_fan_in_variant.py"),
    ("24", "24_fan_out_variant", "24_fan_out_variant.py"),
    ("25", "25_rapid_forwarding_variant", "25_rapid_forwarding_variant.py"),
    ("26", "26_shared_device_variant", "26_shared_device_variant.py"),
    ("27", "27_multi_victim_variant", "27_multi_victim_variant.py"),
    ("28", "28_dormant_activation_variant", "28_dormant_activation_variant.py"),
    ("29", "29_repeated_terminal_variant", "29_repeated_terminal_variant.py"),
    ("30", "30_distributed_cashout_variant", "30_distributed_cashout_variant.py"),
]


class DiscriminationAuditRunner:
    def __init__(self, api_url: str = DEFAULT_API_URL, seed: int = 42):
        self.api_url = api_url
        self.seed = seed
        self.pool = AccountPool(seed=seed)
        self.generator = NormalTrafficGenerator(self.pool, seed=seed)
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "api_url": self.api_url,
            "test_1_normal_only": {},
            "test_2_fraud_only": {},
            "test_3_mixed_stream": {},
            "confusion_matrix": {},
            "score_distributions": {},
        }

    def _get_cases(self) -> List[dict]:
        data = _http_get_json(f"{self.api_url}/cases?role=BANK", timeout=4.0)
        return data.get("cases", []) if data else []

    def run_test_1_normal_only(self, total_txs: int = 1000) -> Dict[str, Any]:
        print("\n" + "=" * 78)
        print("  TEST 1: NORMAL TRAFFIC ONLY (DISCRIMINATION AUDIT)")
        print("=" * 78)
        print(f"  Injecting {total_txs} realistic legitimate transactions...")
        print(f"  Target Pipeline: {self.api_url}")
        print("-" * 78)

        # Register normal account metadata
        _http_post_json(
            f"{self.api_url}/transactions",
            {"transactions": [], "accounts": self.pool.all_metadata},
            timeout=5.0,
        )

        initial_cases = self._get_cases()
        start_time = time.time()

        tx_batch: List[dict] = []
        batch_size = 25
        class_counter = Counter()

        for i in range(total_txs):
            tx, cls_name = self.generator.next_transaction(get_now_utc())
            class_counter[cls_name] += 1
            tx_batch.append(tx)

            if len(tx_batch) >= batch_size or i == total_txs - 1:
                _http_post_json(f"{self.api_url}/transactions", {"transactions": tx_batch}, timeout=5.0)
                tx_batch.clear()

            if (i + 1) % 100 == 0 or i == total_txs - 1:
                sys.stdout.write(f"\r  Progress: {i + 1:5d} / {total_txs} transactions injected...   ")
                sys.stdout.flush()

        duration = time.time() - start_time
        print(f"\n  Finished injecting {total_txs} transactions in {duration:.2f}s ({total_txs/duration:.1f} tx/s)")

        time.sleep(1.0)
        post_cases = self._get_cases()
        normal_account_ids = {a["account_id"] for a in self.pool.all_metadata}

        normal_alerts = []
        tier_counts = Counter()
        for c in post_cases:
            acc_id = c.get("flaggedAccountId", "")
            if acc_id in normal_account_ids:
                normal_alerts.append(c)
                tier = c.get("interventionTier", "UNKNOWN")
                tier_counts[tier] += 1

        fp_cases_count = len(normal_alerts)
        actionable_fp = sum(1 for c in normal_alerts if c.get("interventionTier") in {"TIER_1_FREEZE", "AUTO_FREEZE", "BANK_HOLD", "FIELD_PATROL_DISPATCHED", "SELECTIVE_HOLD"})
        log_only_fp = sum(1 for c in normal_alerts if c.get("interventionTier") in {"LOG_ONLY", "SOFT_NOTIFY"})

        normal_account_scores = {}
        for acc in self.pool.all_metadata:
            acc_id = acc["account_id"]
            c = next((x for x in post_cases if x.get("flaggedAccountId") == acc_id), None)
            score = float(c.get("riskBreakdown", {}).get("totalPercent", 0.0)) if c else 0.0
            normal_account_scores[acc_id] = score

        scores_list = list(normal_account_scores.values())
        scores_list_sorted = sorted(scores_list)

        def pctile(arr, p):
            if not arr:
                return 0.0
            k = (len(arr) - 1) * (p / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return arr[int(k)]
            d0 = arr[int(f)] * (c - k)
            d1 = arr[int(c)] * (k - f)
            return d0 + d1

        p50 = pctile(scores_list_sorted, 50)
        p90 = pctile(scores_list_sorted, 90)
        p95 = pctile(scores_list_sorted, 95)
        p99 = pctile(scores_list_sorted, 99)
        max_score = max(scores_list) if scores_list else 0.0
        mean_score = sum(scores_list) / len(scores_list) if scores_list else 0.0

        buckets = {
            "0-10%": sum(1 for s in scores_list if s <= 10),
            "11-20%": sum(1 for s in scores_list if 10 < s <= 20),
            "21-30%": sum(1 for s in scores_list if 20 < s <= 30),
            "31-40%": sum(1 for s in scores_list if 30 < s <= 40),
            "41-50%": sum(1 for s in scores_list if 40 < s <= 50),
            "51-60%": sum(1 for s in scores_list if 50 < s <= 60),
            ">60%": sum(1 for s in scores_list if s > 60),
        }

        res_test_1 = {
            "total_transactions": total_txs,
            "duration_seconds": round(duration, 2),
            "throughput_tps": round(total_txs / duration, 2),
            "total_normal_accounts": len(self.pool.all_metadata),
            "normal_accounts_alerted": fp_cases_count,
            "actionable_alerts": actionable_fp,
            "log_only_cases": log_only_fp,
            "tier_breakdown": dict(tier_counts),
            "score_stats": {
                "mean": round(mean_score, 2),
                "p50": round(p50, 2),
                "p90": round(p90, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2),
                "max": round(max_score, 2),
            },
            "score_histogram": buckets,
            "false_positive_rate_tx": round((fp_cases_count / max(1, total_txs)) * 100, 4),
            "false_positive_rate_acc": round((fp_cases_count / max(1, len(self.pool.all_metadata))) * 100, 2),
            "actionable_fpr_tx": round((actionable_fp / max(1, total_txs)) * 100, 4),
            "actionable_fpr_acc": round((actionable_fp / max(1, len(self.pool.all_metadata))) * 100, 2),
            "behavioral_class_counts": dict(class_counter),
        }

        print(f"\n  --- TEST 1 RESULTS ---")
        print(f"  Total Normal Transactions:  {total_txs}")
        print(f"  Total Normal Accounts:      {len(self.pool.all_metadata)}")
        print(f"  Normal Accounts Alerted:    {fp_cases_count} (Actionable: {actionable_fp}, Log-only: {log_only_fp})")
        print(f"  Account False Positive Rate: {res_test_1['actionable_fpr_acc']}% (Actionable)")
        print(f"  Mean Risk Score (Normal):   {res_test_1['score_stats']['mean']}% (p90: {p90}%, max: {max_score}%)")
        print(f"  Score Distribution:         {buckets}")
        print("=" * 78)

        self.results["test_1_normal_only"] = res_test_1
        return res_test_1

    def run_test_2_fraud_only(self) -> Dict[str, Any]:
        print("\n" + "=" * 78)
        print("  TEST 2: FRAUD SCENARIOS BASELINE (30 FRAUD SCENARIOS)")
        print("=" * 78)

        scenario_results = []
        tier_counts = Counter()
        scores = []
        start_time = time.time()

        for sid, mod_name, fname in FRAUD_MODULES:
            try:
                mod = importlib.import_module(f"scripts.live_demo.{mod_name}")
                passed = mod.run(api_url=self.api_url, dry_run=False, speed=5.0)

                # Fetch updated cases
                cases = self._get_cases()
                # Find most recent case
                case_data = cases[0] if cases else {}
                risk_score = float(case_data.get("riskBreakdown", {}).get("totalPercent", 0.0)) if case_data else 0.0
                tier = case_data.get("interventionTier", "UNKNOWN") if case_data else "UNKNOWN"
                flagged_acc = case_data.get("flaggedAccountId", "UNKNOWN") if case_data else "UNKNOWN"
                signals = [s.get("name") for s in case_data.get("riskBreakdown", {}).get("signals", [])] if case_data else []

                tier_counts[tier] += 1
                if risk_score > 0:
                    scores.append(risk_score)

                scenario_results.append({
                    "id": sid,
                    "file": fname,
                    "flagged_account": flagged_acc,
                    "passed": passed,
                    "risk_score": risk_score,
                    "tier": tier,
                    "signals": signals,
                })
            except Exception as e:
                log.error(f"Error running scenario {sid}: {e}")
                scenario_results.append({
                    "id": sid,
                    "file": fname,
                    "passed": False,
                    "error": str(e),
                })

        duration = time.time() - start_time
        pass_count = sum(1 for r in scenario_results if r.get("passed"))
        mean_score = sum(scores) / len(scores) if scores else 0.0

        res_test_2 = {
            "total_scenarios": len(FRAUD_MODULES),
            "passed_scenarios": pass_count,
            "detection_rate": round((pass_count / len(FRAUD_MODULES)) * 100, 2),
            "duration_seconds": round(duration, 2),
            "tier_breakdown": dict(tier_counts),
            "score_stats": {
                "mean": round(mean_score, 2),
                "min": min(scores) if scores else 0.0,
                "max": max(scores) if scores else 0.0,
            },
            "scenarios": scenario_results,
        }

        print(f"\n  --- TEST 2 RESULTS ---")
        print(f"  Total Fraud Scenarios:  {len(FRAUD_MODULES)}")
        print(f"  Successfully Detected:  {pass_count} / {len(FRAUD_MODULES)} ({res_test_2['detection_rate']}%)")
        print(f"  Mean Risk Score (Fraud): {res_test_2['score_stats']['mean']}% (Range: {res_test_2['score_stats']['min']}% - {res_test_2['score_stats']['max']}%)")
        print(f"  Tier Breakdown:         {dict(tier_counts)}")
        print("=" * 78)

        self.results["test_2_fraud_only"] = res_test_2
        return res_test_2

    def run_test_3_mixed_stream(self, normal_tx_count: int = 600) -> Dict[str, Any]:
        print("\n" + "=" * 78)
        print("  TEST 3: CONTROLLED MIXED LIVE STREAM EXPERIMENT")
        print("=" * 78)
        print(f"  Executing {normal_tx_count} normal transactions + 10 interleaved fraud scenarios...")
        print("-" * 78)

        test_scenarios = [
            ("01", "01_simple_mule", "01_simple_mule.py"),
            ("02", "02_layering", "02_layering.py"),
            ("03", "03_fan_in", "03_fan_in.py"),
            ("04", "04_fan_out", "04_fan_out.py"),
            ("05", "05_rapid_forwarding", "05_rapid_forwarding.py"),
            ("08", "08_dormant_activation", "08_dormant_activation.py"),
            ("10", "10_distributed_cashout", "10_distributed_cashout.py"),
            ("13", "13_geo_velocity", "13_geo_velocity.py"),
            ("15", "15_shared_kyc_cluster", "15_shared_kyc_cluster.py"),
            ("20", "20_layering_with_distributed_cashout", "20_layering_with_distributed_cashout.py"),
        ]

        normal_interval_txs = normal_tx_count // len(test_scenarios)
        start_time = time.time()
        injected_normal = 0
        scenario_outcomes = []
        batch_size = 20
        tx_batch = []

        for s_idx, (sid, mod_name, fname) in enumerate(test_scenarios):
            # 1. Inject a block of normal transactions
            for _ in range(normal_interval_txs):
                tx, _ = self.generator.next_transaction(get_now_utc())
                tx_batch.append(tx)
                injected_normal += 1
                if len(tx_batch) >= batch_size:
                    _http_post_json(f"{self.api_url}/transactions", {"transactions": tx_batch}, timeout=4.0)
                    tx_batch.clear()

            if tx_batch:
                _http_post_json(f"{self.api_url}/transactions", {"transactions": tx_batch}, timeout=4.0)
                tx_batch.clear()

            # 2. Inject Fraud Scenario
            print(f"\n  [*] [{s_idx+1}/{len(test_scenarios)}] Injecting Fraud Scenario {sid} ({fname})...")
            try:
                mod = importlib.import_module(f"scripts.live_demo.{mod_name}")
                passed = mod.run(api_url=self.api_url, dry_run=False, speed=5.0)
                cases = self._get_cases()
                cdata = cases[0] if cases else {}
                scenario_outcomes.append({
                    "id": sid,
                    "passed": passed,
                    "account": cdata.get("flaggedAccountId", "N/A"),
                    "score": cdata.get("riskBreakdown", {}).get("totalPercent", 0),
                    "tier": cdata.get("interventionTier", "N/A"),
                })
            except Exception as e:
                log.error(f"Failed scenario {sid}: {e}")
                scenario_outcomes.append({"id": sid, "passed": False, "error": str(e)})

        remaining = normal_tx_count - injected_normal
        if remaining > 0:
            rem_batch = [self.generator.next_transaction(get_now_utc())[0] for _ in range(remaining)]
            _http_post_json(f"{self.api_url}/transactions", {"transactions": rem_batch}, timeout=4.0)
            injected_normal += remaining

        duration = time.time() - start_time
        time.sleep(1.0)

        all_cases = self._get_cases()
        normal_account_ids = {a["account_id"] for a in self.pool.all_metadata}

        tp = sum(1 for sc in scenario_outcomes if sc.get("passed"))
        fn = len(test_scenarios) - tp

        fp_normal_cases = [c for c in all_cases if c.get("flaggedAccountId") in normal_account_ids and c.get("interventionTier") in {"TIER_1_FREEZE", "AUTO_FREEZE", "BANK_HOLD", "FIELD_PATROL_DISPATCHED", "SELECTIVE_HOLD"}]
        fp = len(fp_normal_cases)
        tn = len(self.pool.all_metadata) - fp

        precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = (fp / (fp + tn)) * 100 if (fp + tn) > 0 else 0.0
        quiet_rate = (tn / len(self.pool.all_metadata)) * 100 if self.pool.all_metadata else 100.0

        res_test_3 = {
            "total_normal_transactions": injected_normal,
            "total_fraud_scenarios": len(test_scenarios),
            "duration_seconds": round(duration, 2),
            "confusion_matrix": {
                "TP": tp,
                "FP": fp,
                "TN": tn,
                "FN": fn,
            },
            "metrics": {
                "precision": round(precision, 2),
                "recall": round(recall, 2),
                "f1_score": round(f1, 2),
                "false_positive_rate": round(fpr, 2),
                "scenario_detection_rate": round(recall, 2),
                "normal_quiet_rate": round(quiet_rate, 2),
            },
            "scenario_outcomes": scenario_outcomes,
        }

        print(f"\n  --- TEST 3 MIXED STREAM RESULTS ---")
        print(f"  Normal Transactions Injected: {injected_normal}")
        print(f"  Fraud Scenarios Injected:     {len(test_scenarios)}")
        print(f"  Confusion Matrix:             TP={tp}, FP={fp}, TN={tn}, FN={fn}")
        print(f"  Precision:                    {res_test_3['metrics']['precision']}%")
        print(f"  Recall (Detection Rate):      {res_test_3['metrics']['recall']}%")
        print(f"  F1 Score:                     {res_test_3['metrics']['f1_score']}%")
        print(f"  False Positive Rate (FPR):    {res_test_3['metrics']['false_positive_rate']}%")
        print(f"  Normal Quiet Rate:            {res_test_3['metrics']['normal_quiet_rate']}%")
        print("=" * 78)

        self.results["test_3_mixed_stream"] = res_test_3
        return res_test_3

    def run_all(self, normal_txs: int = 1000) -> Dict[str, Any]:
        self.run_test_1_normal_only(total_txs=normal_txs)
        self.run_test_2_fraud_only()
        self.run_test_3_mixed_stream(normal_tx_count=600)

        out_path = REPO_ROOT / "scripts" / "live_demo" / "discrimination_audit_results.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n[+] Saved audit results to {out_path}")

        return self.results


def main():
    parser = argparse.ArgumentParser(description="Run CyberShield Detector Discrimination Audit")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"Backend API URL (default: {DEFAULT_API_URL})")
    parser.add_argument("--normal-txs", type=int, default=1000, help="Number of normal txs for Test 1 (default: 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Seed for generator reproducibility")
    args = parser.parse_args()

    runner = DiscriminationAuditRunner(api_url=args.api_url, seed=args.seed)
    runner.run_all(normal_txs=args.normal_txs)


if __name__ == "__main__":
    main()
