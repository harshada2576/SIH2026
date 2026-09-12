#!/usr/bin/env python3
"""
Scenario 30: 4-Way Multi-Terminal Cashout Distribution Variant
Aggregator receives multi-victim funds and splits into 4 cashout mules targeting mixed ATM & AEPS points.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    aggr = f"ACC-AGGR-V30-{ts_str}"
    dev = f"DEV-V30-RING-{ts_str}"

    accounts = [
        make_account(aggr, tier="aggregator", age_days=1, terminals=["ATM-HDFC-Ce-001", "ATM-ICICI-Ce-004", "AEPS-BCR-002"], device=dev),
    ]

    txs = [
        # Aggregation Inflows (4 inflows)
        make_transaction(f"TXN-V30-{ts_str}-01", f"ACC-VIC-A-{ts_str}", aggr, 50000.0, now - timedelta(seconds=28), "UPI", dev),
        make_transaction(f"TXN-V30-{ts_str}-02", f"ACC-VIC-B-{ts_str}", aggr, 55000.0, now - timedelta(seconds=22), "UPI", dev),
        make_transaction(f"TXN-V30-{ts_str}-03", f"ACC-VIC-C-{ts_str}", aggr, 50000.0, now - timedelta(seconds=16), "UPI", dev),
        make_transaction(f"TXN-V30-{ts_str}-04", f"ACC-VIC-D-{ts_str}", aggr, 45000.0, now - timedelta(seconds=10), "UPI", dev),
        # 4-Way Cashout Split
        make_transaction(f"TXN-V30-{ts_str}-05", aggr, f"ACC-CASH-1-{ts_str}", 48000.0, now - timedelta(seconds=6), "UPI", dev),
        make_transaction(f"TXN-V30-{ts_str}-06", aggr, f"ACC-CASH-2-{ts_str}", 47000.0, now - timedelta(seconds=4), "UPI", dev),
        make_transaction(f"TXN-V30-{ts_str}-07", aggr, f"ACC-CASH-3-{ts_str}", 48000.0, now - timedelta(seconds=2), "UPI", dev),
        make_transaction(f"TXN-V30-{ts_str}-08", aggr, f"ACC-CASH-4-{ts_str}", 50000.0, now - timedelta(seconds=1), "UPI", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="30 — 4-Way Multi-Terminal Cashout Variant",
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
