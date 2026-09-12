#!/usr/bin/env python3
"""
Scenario 13: Impossible Geo-Velocity Anomaly
Mule account registers rapid transactions and terminal interactions across
distant cities within seconds, paired with high velocity and rapid fund forwarding.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-GEO-MULE-{ts_str}"
    cashout = f"ACC-GEO-CASH-{ts_str}"
    dev = f"DEV-GEO-RING-{ts_str}"

    accounts = [
        make_account(mule, tier="mule_l1", age_days=2, terminals=["ATM-DEL-001", "ATM-BLR-001", "ATM-HDFC-Ce-001"], device=dev),
        make_account(cashout, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-GEO-{ts_str}-01", f"ACC-VIC-DEL-{ts_str}", mule, 50000.0, now - timedelta(seconds=25), "UPI", dev),
        make_transaction(f"TXN-GEO-{ts_str}-02", f"ACC-VIC-BLR-{ts_str}", mule, 55000.0, now - timedelta(seconds=18), "UPI", dev),
        make_transaction(f"TXN-GEO-{ts_str}-03", f"ACC-VIC-HYD-{ts_str}", mule, 45000.0, now - timedelta(seconds=12), "UPI", dev),
        make_transaction(f"TXN-GEO-{ts_str}-04", f"ACC-VIC-MUM-{ts_str}", mule, 40000.0, now - timedelta(seconds=7), "UPI", dev),
        make_transaction(f"TXN-GEO-{ts_str}-05", mule, cashout, 185000.0, now - timedelta(seconds=2), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="13 — Impossible Geo-Velocity Anomaly",
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
