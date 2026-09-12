#!/usr/bin/env python3
"""
scripts/live_demo/run_all_live_demos.py — Executes live demo scenarios sequentially.
Supports running Set 1 (01-10), Set 2 (11-20), Set 3 (21-30), or all 30 scenarios.
SIH26184 — Predictive Cash Egress Interception
"""
import argparse
import importlib
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SET_1_MODULES = [
    "01_simple_mule",
    "02_layering",
    "03_fan_in",
    "04_fan_out",
    "05_rapid_forwarding",
    "06_shared_device",
    "07_multi_victim_common_mule",
    "08_dormant_activation",
    "09_repeated_atm_targeting",
    "10_distributed_cashout",
]

SET_2_MODULES = [
    "11_cross_city_mule",
    "12_probing_then_large",
    "13_geo_velocity",
    "14_fan_in_fan_out",
    "15_shared_kyc_cluster",
    "16_concurrent_campaign",
    "17_amount_escalation",
    "18_rapid_multi_account_cashout",
    "19_cross_device_mule_chain",
    "20_layering_with_distributed_cashout",
]

SET_3_MODULES = [
    "21_simple_mule_variant",
    "22_layering_variant",
    "23_fan_in_variant",
    "24_fan_out_variant",
    "25_rapid_forwarding_variant",
    "26_shared_device_variant",
    "27_multi_victim_variant",
    "28_dormant_activation_variant",
    "29_repeated_terminal_variant",
    "30_distributed_cashout_variant",
]

def main():
    parser = argparse.ArgumentParser(description="Run CyberShield Live Demo Scenarios")
    parser.add_argument("--set", choices=["1", "2", "3", "all"], default="all", help="Which set of fraud scenarios to execute")
    parser.add_argument("--all", action="store_true", help="Execute all 30 scenarios across Sets 1, 2, and 3")
    parser.add_argument("--api-url", default="http://127.0.0.1:5003", help="Backend API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without injecting into pipeline")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed multiplier for simulation delays (default 1.0)")
    args = parser.parse_args()

    modules_to_run = []
    if args.set == "1" and not args.all:
        modules_to_run = SET_1_MODULES
        set_title = "SET 1: CORE HEURISTIC SCENARIOS (01 - 10)"
    elif args.set == "2" and not args.all:
        modules_to_run = SET_2_MODULES
        set_title = "SET 2: ADVANCED FRAUD SCENARIOS (11 - 20)"
    elif args.set == "3" and not args.all:
        modules_to_run = SET_3_MODULES
        set_title = "SET 3: VARIANTS & STRESS SCENARIOS (21 - 30)"
    else:
        modules_to_run = SET_1_MODULES + SET_2_MODULES + SET_3_MODULES
        set_title = "ALL 30 LIVE DEMO TRANSACTION INJECTION SCENARIOS"

    print("\n" + "=" * 78)
    print(f"  SIH26184 — EXECUTING {set_title}")
    print(f"  Target Backend: {args.api_url} | Dry-Run: {args.dry_run} | Speed: {args.speed}x")
    print("=" * 78 + "\n")

    results = []
    start_time = time.time()

    for mod_name in modules_to_run:
        try:
            mod = importlib.import_module(f"scripts.live_demo.{mod_name}")
            ok = mod.run(api_url=args.api_url, dry_run=args.dry_run, speed=args.speed)
            results.append((mod_name, "PASS" if ok else "FAIL"))
        except Exception as e:
            print(f"[ERROR in {mod_name}]: {e}")
            results.append((mod_name, "ERROR"))
        if not args.dry_run:
            time.sleep(max(0.05, 0.3 / args.speed))

    elapsed = time.time() - start_time
    print("\n" + "=" * 78)
    print(f"  FINAL LIVE DEMO EXECUTION SUMMARY REPORT — {set_title}")
    print("=" * 78)
    print(f"  {'#':<3} | {'Scenario Module Name':<38} | {'Result':<8}")
    print("  " + "-" * 54)

    passed_count = sum(1 for _, res in results if res == "PASS")
    for idx, (name, res) in enumerate(results, 1):
        status_icon = "✓ PASS" if res == "PASS" else "✗ " + res
        print(f"  {idx:<3} | {name:<38} | {status_icon:<8}")

    print("  " + "-" * 54)
    pass_rate = (passed_count / len(results) * 100) if results else 0.0
    print(f"  Total Passed: {passed_count}/{len(results)} ({pass_rate:.1f}%) in {elapsed:.2f}s")
    print("=" * 78 + "\n")

    if passed_count < len(results):
        sys.exit(1)

if __name__ == "__main__":
    main()
