#!/usr/bin/env python3
"""
Scenario 27: Multi-Victim Urgent Scam Feeder Variant
5 victims tricked by urgent KYC-expiry phishing simultaneously deposit into one central receiver mule.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-SCAM-HUB-{ts_str}"
    cashout = f"ACC-SCAM-CASH-{ts_str}"
    dev = f"DEV-SCAM-RING-{ts_str}"

    accounts = [
        make_account(mule, tier="aggregator", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-V27-{ts_str}-01", f"ACC-VIC-1-{ts_str}", mule, 45000.0, now - timedelta(seconds=24), "UPI", dev),
        make_transaction(f"TXN-V27-{ts_str}-02", f"ACC-VIC-2-{ts_str}", mule, 50000.0, now - timedelta(seconds=19), "UPI", dev),
        make_transaction(f"TXN-V27-{ts_str}-03", f"ACC-VIC-3-{ts_str}", mule, 40000.0, now - timedelta(seconds=14), "UPI", dev),
        make_transaction(f"TXN-V27-{ts_str}-04", f"ACC-VIC-4-{ts_str}", mule, 35000.0, now - timedelta(seconds=9), "UPI", dev),
        make_transaction(f"TXN-V27-{ts_str}-05", f"ACC-VIC-5-{ts_str}", mule, 55000.0, now - timedelta(seconds=4), "UPI", dev),
        make_transaction(f"TXN-V27-{ts_str}-06", mule, cashout, 220000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="27 — Multi-Victim Scam Feeder Variant",
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
