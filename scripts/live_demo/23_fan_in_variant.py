#!/usr/bin/env python3
"""
Scenario 23: High-Frequency Fan-In Avalanche Variant
6 separate victim accounts transfer funds simultaneously into a single collector mule within 25 seconds.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-MULE-V23-{ts_str}"
    cashout = f"ACC-CASH-V23-{ts_str}"
    dev = f"DEV-V23-RING-{ts_str}"

    accounts = [
        make_account(mule, tier="aggregator", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-V23-{ts_str}-01", f"ACC-V1-{ts_str}", mule, 28000.0, now - timedelta(seconds=25), "UPI", dev),
        make_transaction(f"TXN-V23-{ts_str}-02", f"ACC-V2-{ts_str}", mule, 32000.0, now - timedelta(seconds=21), "UPI", dev),
        make_transaction(f"TXN-V23-{ts_str}-03", f"ACC-V3-{ts_str}", mule, 30000.0, now - timedelta(seconds=17), "UPI", dev),
        make_transaction(f"TXN-V23-{ts_str}-04", f"ACC-V4-{ts_str}", mule, 29000.0, now - timedelta(seconds=13), "UPI", dev),
        make_transaction(f"TXN-V23-{ts_str}-05", f"ACC-V5-{ts_str}", mule, 31000.0, now - timedelta(seconds=9), "UPI", dev),
        make_transaction(f"TXN-V23-{ts_str}-06", f"ACC-V6-{ts_str}", mule, 35000.0, now - timedelta(seconds=5), "UPI", dev),
        make_transaction(f"TXN-V23-{ts_str}-07", mule, cashout, 180000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="23 — High-Frequency Fan-In Avalanche",
        transactions=txs,
        target_flagged_account=mule,
        api_url=api_url,
        account_metadata=accounts,
        dry_run=dry_run,
        speed=speed,
    )
    return success

if __name__ == "__main__":
    api_url, dry_run, speed = parse_cli_args()
    run(api_url=api_url, dry_run=dry_run, speed=speed)
