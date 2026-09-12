#!/usr/bin/env python3
"""
Scenario 04: Rapid Multi-Destination Fan-Out
A high-value deposit is fragmented across multiple mule accounts within seconds.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    hub = f"ACC-HUB-FOUT-{ts_str}"
    dev = f"DEV-FOUT-RING-{ts_str}"

    accounts = [
        make_account(hub, tier="aggregator", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-FOUT-{ts_str}-00A", f"ACC-VIC-1-{ts_str}", hub, 60000.0, now - timedelta(seconds=24), "UPI", dev),
        make_transaction(f"TXN-FOUT-{ts_str}-00B", f"ACC-VIC-2-{ts_str}", hub, 65000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-FOUT-{ts_str}-00C", f"ACC-VIC-3-{ts_str}", hub, 55000.0, now - timedelta(seconds=16), "UPI", dev),
        make_transaction(f"TXN-FOUT-{ts_str}-01", hub, f"ACC-M1-FOUT-{ts_str}", 45000.0, now - timedelta(seconds=10), "UPI", dev),
        make_transaction(f"TXN-FOUT-{ts_str}-02", hub, f"ACC-M2-FOUT-{ts_str}", 45000.0, now - timedelta(seconds=8), "UPI", dev),
        make_transaction(f"TXN-FOUT-{ts_str}-03", hub, f"ACC-M3-FOUT-{ts_str}", 45000.0, now - timedelta(seconds=6), "UPI", dev),
        make_transaction(f"TXN-FOUT-{ts_str}-04", hub, f"ACC-M4-FOUT-{ts_str}", 42000.0, now - timedelta(seconds=2), "UPI", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="04 — Rapid Multi-Destination Fan-Out",
        transactions=txs,
        target_flagged_account=hub,
        api_url=api_url,
        account_metadata=accounts,
        dry_run=dry_run,
        speed=speed,
    )
    return success

if __name__ == "__main__":
    api_url, dry_run, speed = parse_cli_args()
    run(api_url=api_url, dry_run=dry_run, speed=speed)
