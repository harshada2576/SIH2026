#!/usr/bin/env python3
"""
Scenario 25: Sub-3-Second Ultra-Rapid Forwarding Variant
Mule receives rapid funds and forwards 99.8% to a terminal cash-out destination in under 3 seconds.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-MULE-V25-{ts_str}"
    cashout = f"ACC-CASH-V25-{ts_str}"
    dev = f"DEV-V25-RING-{ts_str}"

    accounts = [
        make_account(mule, tier="mule_l1", age_days=1, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
        make_account(cashout, tier="mule_l2", age_days=2, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-V25-{ts_str}-01", f"ACC-VIC-A-{ts_str}", mule, 45000.0, now - timedelta(seconds=16), "UPI", dev),
        make_transaction(f"TXN-V25-{ts_str}-02", f"ACC-VIC-B-{ts_str}", mule, 50000.0, now - timedelta(seconds=12), "UPI", dev),
        make_transaction(f"TXN-V25-{ts_str}-03", f"ACC-VIC-C-{ts_str}", mule, 50000.0, now - timedelta(seconds=8), "UPI", dev),
        make_transaction(f"TXN-V25-{ts_str}-04", f"ACC-VIC-D-{ts_str}", mule, 50000.0, now - timedelta(seconds=4), "UPI", dev),
        make_transaction(f"TXN-V25-{ts_str}-05", mule, cashout, 194000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="25 — Ultra-Rapid Forwarding Variant",
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
