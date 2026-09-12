#!/usr/bin/env python3
"""
Scenario 07: Multi-Victim Convergence on Common Mule
Unrelated victims across India simultaneously transfer funds into one mule.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-MULE-MVIC-{ts_str}"
    cashout = f"ACC-CASH-MVIC-{ts_str}"
    dev = f"DEV-MVIC-RING-{ts_str}"

    accounts = [
        make_account(mule, tier="aggregator", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-MV-{ts_str}-01", f"ACC-VIC-DELHI-{ts_str}", mule, 50000.0, now - timedelta(seconds=22), "UPI", dev),
        make_transaction(f"TXN-MV-{ts_str}-02", f"ACC-VIC-MUMBAI-{ts_str}", mule, 45000.0, now - timedelta(seconds=17), "UPI", dev),
        make_transaction(f"TXN-MV-{ts_str}-03", f"ACC-VIC-KOLKATA-{ts_str}", mule, 40000.0, now - timedelta(seconds=12), "UPI", dev),
        make_transaction(f"TXN-MV-{ts_str}-04", f"ACC-VIC-CHENNAI-{ts_str}", mule, 42000.0, now - timedelta(seconds=7), "UPI", dev),
        make_transaction(f"TXN-MV-{ts_str}-05", mule, cashout, 175000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="07 — Multi-Victim Common Mule Convergence",
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
