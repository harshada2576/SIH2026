#!/usr/bin/env python3
"""
Scenario 24: High-Velocity Fan-Out Split Variant
Aggregator receives high-value fraudulent injection and splits it across 5 runner mules simultaneously.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    vic = f"ACC-VIC-V24-{ts_str}"
    aggr = f"ACC-AGGR-V24-{ts_str}"
    dev = f"DEV-V24-RING-{ts_str}"

    accounts = [
        make_account(aggr, tier="aggregator", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
    ]

    txs = [
        # Inflows (3 distinct senders)
        make_transaction(f"TXN-V24-{ts_str}-00", vic, aggr, 120000.0, now - timedelta(seconds=25), "IMPS", dev),
        make_transaction(f"TXN-V24-{ts_str}-00B", f"ACC-VIC-B-{ts_str}", aggr, 45000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-V24-{ts_str}-00C", f"ACC-VIC-C-{ts_str}", aggr, 40000.0, now - timedelta(seconds=16), "UPI", dev),
        # 5-way rapid fan-out egress
        make_transaction(f"TXN-V24-{ts_str}-01", aggr, f"ACC-M1-V24-{ts_str}", 40000.0, now - timedelta(seconds=12), "UPI", dev),
        make_transaction(f"TXN-V24-{ts_str}-02", aggr, f"ACC-M2-V24-{ts_str}", 38000.0, now - timedelta(seconds=9), "UPI", dev),
        make_transaction(f"TXN-V24-{ts_str}-03", aggr, f"ACC-M3-V24-{ts_str}", 42000.0, now - timedelta(seconds=6), "UPI", dev),
        make_transaction(f"TXN-V24-{ts_str}-04", aggr, f"ACC-M4-V24-{ts_str}", 39000.0, now - timedelta(seconds=3), "UPI", dev),
        make_transaction(f"TXN-V24-{ts_str}-05", aggr, f"ACC-M5-V24-{ts_str}", 42000.0, now - timedelta(seconds=1), "UPI", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="24 — High-Velocity Fan-Out Split Variant",
        transactions=txs,
        target_flagged_account=aggr,
        api_url=api_url,
        account_metadata=accounts,
        dry_run=dry_run,
        speed=speed,
    )
    return success

if __name__ == "__main__":
    api_url, dry_run, speed = parse_cli_args()
    run(api_url=api_url, dry_run=dry_run, speed=speed)
