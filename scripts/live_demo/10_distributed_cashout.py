#!/usr/bin/env python3
"""
Scenario 10: Distributed Multi-Terminal Cashout
Aggregator receives pooled funds and fragments them to multiple withdrawal nodes targeting different ATMs.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    aggr = f"ACC-AGGR-DCASH-{ts_str}"
    dev = f"DEV-DCASH-RING-{ts_str}"

    accounts = [
        make_account(aggr, tier="aggregator", age_days=2, terminals=["ATM-HDFC-Ce-001", "ATM-ICICI-Ce-004", "AEPS-BCR-002"], device=dev),
    ]

    txs = [
        # Aggregation inflows (4 inflows)
        make_transaction(f"TXN-DC-{ts_str}-01", f"ACC-VIC-A-{ts_str}", aggr, 50000.0, now - timedelta(seconds=28), "UPI", dev),
        make_transaction(f"TXN-DC-{ts_str}-02", f"ACC-VIC-B-{ts_str}", aggr, 50000.0, now - timedelta(seconds=22), "UPI", dev),
        make_transaction(f"TXN-DC-{ts_str}-03", f"ACC-VIC-C-{ts_str}", aggr, 50000.0, now - timedelta(seconds=16), "UPI", dev),
        make_transaction(f"TXN-DC-{ts_str}-04", f"ACC-VIC-D-{ts_str}", aggr, 45000.0, now - timedelta(seconds=10), "UPI", dev),
        # Distributed cashouts
        make_transaction(f"TXN-DC-{ts_str}-05", aggr, f"ACC-CASH-A-{ts_str}", 48000.0, now - timedelta(seconds=6), "UPI", dev),
        make_transaction(f"TXN-DC-{ts_str}-06", aggr, f"ACC-CASH-B-{ts_str}", 48000.0, now - timedelta(seconds=4), "UPI", dev),
        make_transaction(f"TXN-DC-{ts_str}-07", aggr, f"ACC-CASH-C-{ts_str}", 50000.0, now - timedelta(seconds=1), "UPI", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="10 — Distributed Multi-Terminal Cashout",
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
