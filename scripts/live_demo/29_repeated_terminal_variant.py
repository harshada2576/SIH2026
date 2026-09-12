#!/usr/bin/env python3
"""
Scenario 29: Concentrated ATM Terminal Exhaustion Variant
Successive mule conduits aggressively funnel funds toward the same physical ATM terminal corridor.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-ATM-V29-{ts_str}"
    cashout = f"ACC-CASH-V29-{ts_str}"
    dev = f"DEV-ATM-V29-{ts_str}"

    accounts = [
        make_account(mule, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
        make_account(cashout, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-V29-{ts_str}-01", f"ACC-VIC-1-{ts_str}", mule, 45000.0, now - timedelta(seconds=24), "UPI", dev),
        make_transaction(f"TXN-V29-{ts_str}-02", f"ACC-VIC-2-{ts_str}", mule, 45000.0, now - timedelta(seconds=18), "UPI", dev),
        make_transaction(f"TXN-V29-{ts_str}-03", f"ACC-VIC-3-{ts_str}", mule, 40000.0, now - timedelta(seconds=12), "UPI", dev),
        make_transaction(f"TXN-V29-{ts_str}-04", f"ACC-VIC-4-{ts_str}", mule, 35000.0, now - timedelta(seconds=6), "UPI", dev),
        make_transaction(f"TXN-V29-{ts_str}-05", mule, cashout, 160000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="29 — Concentrated ATM Corridor Sweep Variant",
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
