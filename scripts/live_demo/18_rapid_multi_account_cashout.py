#!/usr/bin/env python3
"""
Scenario 18: Coordinated Multi-Account ATM Cashout Sweep
Stolen funds are dispersed to multiple accomplice mules, which simultaneously target
high-density ATM corridors for coordinated cash withdrawals.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    m1 = f"ACC-M1-SWP-{ts_str}"
    dev = f"DEV-SWP-RING-{ts_str}"

    accounts = [
        make_account(m1, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
    ]

    txs = [
        # Victim transfers to mule 1
        make_transaction(f"TXN-SWP-{ts_str}-01", f"ACC-VIC-1-{ts_str}", m1, 55000.0, now - timedelta(seconds=26), "UPI", dev),
        make_transaction(f"TXN-SWP-{ts_str}-02", f"ACC-VIC-2-{ts_str}", m1, 50000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-SWP-{ts_str}-03", f"ACC-VIC-3-{ts_str}", m1, 45000.0, now - timedelta(seconds=14), "UPI", dev),
        make_transaction(f"TXN-SWP-{ts_str}-04", f"ACC-VIC-4-{ts_str}", m1, 40000.0, now - timedelta(seconds=8), "UPI", dev),
        # Coordinated forwarding
        make_transaction(f"TXN-SWP-{ts_str}-05", m1, f"ACC-CASH-A-{ts_str}", 185000.0, now - timedelta(seconds=2), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="18 — Coordinated Multi-Account Cashout Sweep",
        transactions=txs,
        target_flagged_account=m1,
        api_url=api_url,
        account_metadata=accounts,
        dry_run=dry_run,
        speed=speed,
    )
    return success

if __name__ == "__main__":
    api_url, dry_run, speed = parse_cli_args()
    run(api_url=api_url, dry_run=dry_run, speed=speed)
