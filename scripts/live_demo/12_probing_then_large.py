#!/usr/bin/env python3
"""
Scenario 12: Micro-Probing Followed by Rapid Large-Scale Burst
Fraudster performs small probe transactions (₹100, ₹250) to test account liveness/limits,
immediately followed by rapid high-value transfers and 99% forward egress.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-PRB-MULE-{ts_str}"
    cashout = f"ACC-PRB-CASH-{ts_str}"
    dev = f"DEV-PRB-RING-{ts_str}"

    accounts = [
        make_account(mule, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
        make_account(cashout, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        # Micro probe transactions
        make_transaction(f"TXN-PRB-{ts_str}-01", f"ACC-VIC-PRB1-{ts_str}", mule, 100.0, now - timedelta(seconds=35), "UPI", dev),
        make_transaction(f"TXN-PRB-{ts_str}-02", f"ACC-VIC-PRB2-{ts_str}", mule, 250.0, now - timedelta(seconds=28), "UPI", dev),
        # Large burst inflows
        make_transaction(f"TXN-PRB-{ts_str}-03", f"ACC-VIC-PRB3-{ts_str}", mule, 60000.0, now - timedelta(seconds=18), "IMPS", dev),
        make_transaction(f"TXN-PRB-{ts_str}-04", f"ACC-VIC-PRB4-{ts_str}", mule, 65000.0, now - timedelta(seconds=12), "IMPS", dev),
        # Rapid cashout forward (99%)
        make_transaction(f"TXN-PRB-{ts_str}-05", mule, cashout, 124000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="12 — Micro-Probing Followed by Rapid Burst",
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
