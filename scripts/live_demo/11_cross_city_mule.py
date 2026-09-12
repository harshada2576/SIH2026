#!/usr/bin/env python3
"""
Scenario 11: Cross-City Mule Migration
High-value funds flow into an account in Bengaluru, which routes through Chennai
and attempts cash egress in Mumbai within seconds, triggering velocity, fan-in, and amount movement.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-CC-MULE-{ts_str}"
    cashout = f"ACC-CC-CASH-{ts_str}"
    dev = f"DEV-CC-RING-{ts_str}"

    accounts = [
        make_account(mule, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001", "ATM-BLR-002", "ATM-ICICI-Ce-004"], device=dev),
        make_account(cashout, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-CC-{ts_str}-01", f"ACC-VIC-BLR-{ts_str}", mule, 48000.0, now - timedelta(seconds=22), "UPI", dev),
        make_transaction(f"TXN-CC-{ts_str}-02", f"ACC-VIC-CHN-{ts_str}", mule, 52000.0, now - timedelta(seconds=17), "UPI", dev),
        make_transaction(f"TXN-CC-{ts_str}-03", f"ACC-VIC-MUM-{ts_str}", mule, 45000.0, now - timedelta(seconds=12), "UPI", dev),
        make_transaction(f"TXN-CC-{ts_str}-04", f"ACC-VIC-DEL-{ts_str}", mule, 40000.0, now - timedelta(seconds=7), "UPI", dev),
        make_transaction(f"TXN-CC-{ts_str}-05", mule, cashout, 180000.0, now - timedelta(seconds=2), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="11 — Cross-City Mule Migration",
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
