#!/usr/bin/env python3
"""
Scenario 01: Simple Mule & Rapid Egress
Victim accounts rapidly transfer ₹1,20,000 into a newly activated mule account,
which forwards 98% of the funds to a cash-out destination within seconds.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-MULE-SMP-{ts_str}"
    dev = f"DEV-MULE-RING-{ts_str}"
    cashout_dest = f"ACC-CASH-SMP-{ts_str}"

    accounts = [
        make_account(mule, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002"], device=dev),
        make_account(cashout_dest, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-SMP-{ts_str}-01", f"ACC-VIC-01-{ts_str}", mule, 45000.0, now - timedelta(seconds=25), "UPI", dev),
        make_transaction(f"TXN-SMP-{ts_str}-02", f"ACC-VIC-02-{ts_str}", mule, 40000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-SMP-{ts_str}-03", f"ACC-VIC-03-{ts_str}", mule, 35000.0, now - timedelta(seconds=15), "UPI", dev),
        make_transaction(f"TXN-SMP-{ts_str}-04", f"ACC-VIC-04-{ts_str}", mule, 30000.0, now - timedelta(seconds=10), "UPI", dev),
        make_transaction(f"TXN-SMP-{ts_str}-05", mule, cashout_dest, 147000.0, now - timedelta(seconds=2), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="01 — Simple Mule & Rapid Egress",
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
