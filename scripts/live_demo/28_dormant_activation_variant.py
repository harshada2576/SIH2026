#!/usr/bin/env python3
"""
Scenario 28: Long-Dormant Account Reactivation Variant
A 450-day-old inactive mule account is abruptly reactivated with ₹2,20,000 inflow and instant egress.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    dormant = f"ACC-DORM-V28-{ts_str}"
    cashout = f"ACC-CASH-V28-{ts_str}"
    dev = f"DEV-DORM-V28-{ts_str}"

    accounts = [
        make_account(dormant, tier="mule_l1", age_days=450, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
        make_account(cashout, tier="mule_l2", age_days=2, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        # 5 distinct senders for Fan-in = 12 pts
        make_transaction(f"TXN-V28-{ts_str}-01", f"ACC-VIC-1-{ts_str}", dormant, 45000.0, now - timedelta(seconds=25), "UPI", dev),
        make_transaction(f"TXN-V28-{ts_str}-02", f"ACC-VIC-2-{ts_str}", dormant, 45000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-V28-{ts_str}-03", f"ACC-VIC-3-{ts_str}", dormant, 40000.0, now - timedelta(seconds=15), "UPI", dev),
        make_transaction(f"TXN-V28-{ts_str}-04", f"ACC-VIC-4-{ts_str}", dormant, 45000.0, now - timedelta(seconds=10), "UPI", dev),
        make_transaction(f"TXN-V28-{ts_str}-05", f"ACC-VIC-5-{ts_str}", dormant, 45000.0, now - timedelta(seconds=5), "UPI", dev),
        make_transaction(f"TXN-V28-{ts_str}-06", dormant, cashout, 215000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="28 — Long-Dormant Reactivation Variant",
        transactions=txs,
        target_flagged_account=dormant,
        api_url=api_url,
        account_metadata=accounts,
        dry_run=dry_run,
        speed=speed,
    )
    return success

if __name__ == "__main__":
    api_url, dry_run, speed = parse_cli_args()
    run(api_url=api_url, dry_run=dry_run, speed=speed)
