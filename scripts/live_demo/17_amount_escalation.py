#!/usr/bin/env python3
"""
Scenario 17: Progressive Amount Escalation Ladder
Mule receives rapidly escalating transactions (₹5k -> ₹20k -> ₹50k -> ₹1,00,000) within 30s
to bypass static single-transaction amount rules, followed by immediate 98% cashout.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    mule = f"ACC-ESC-MULE-{ts_str}"
    cashout = f"ACC-ESC-CASH-{ts_str}"
    dev = f"DEV-ESC-RING-{ts_str}"

    accounts = [
        make_account(mule, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
        make_account(cashout, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        # Stepping Ladder Inflows (4 distinct senders)
        make_transaction(f"TXN-ESC-{ts_str}-01", f"ACC-VIC-E1-{ts_str}", mule, 15000.0, now - timedelta(seconds=28), "UPI", dev),
        make_transaction(f"TXN-ESC-{ts_str}-02", f"ACC-VIC-E2-{ts_str}", mule, 30000.0, now - timedelta(seconds=21), "UPI", dev),
        make_transaction(f"TXN-ESC-{ts_str}-03", f"ACC-VIC-E3-{ts_str}", mule, 50000.0, now - timedelta(seconds=14), "UPI", dev),
        make_transaction(f"TXN-ESC-{ts_str}-04", f"ACC-VIC-E4-{ts_str}", mule, 100000.0, now - timedelta(seconds=7), "IMPS", dev),
        # Final Aggregate Egress (₹1,90,000 / ₹1,95,000 = ~97.5%)
        make_transaction(f"TXN-ESC-{ts_str}-05", mule, cashout, 190000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="17 — Progressive Amount Escalation Ladder",
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
