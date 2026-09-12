#!/usr/bin/env python3
"""
Scenario 16: Concurrent Dual-Campaign Fraud Blitz
Two coordinated phishing campaigns run in parallel targeting different victim groups,
converging on high-velocity mules with immediate cross-forwarding.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    hub_a = f"ACC-CMPA-HUB-{ts_str}"
    hub_b = f"ACC-CMPB-HUB-{ts_str}"
    cashout = f"ACC-CMP-CASH-{ts_str}"
    dev = f"DEV-CMP-RING-{ts_str}"

    accounts = [
        make_account(hub_a, tier="aggregator", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
        make_account(hub_b, tier="aggregator", age_days=2, terminals=["ATM-ICICI-Ce-004"], device=dev),
    ]

    txs = [
        # Campaign Alpha (4 inflows to hub_a)
        make_transaction(f"TXN-CMPA-{ts_str}-01", f"ACC-VIC-A1-{ts_str}", hub_a, 45000.0, now - timedelta(seconds=28), "UPI", dev),
        make_transaction(f"TXN-CMPA-{ts_str}-02", f"ACC-VIC-A2-{ts_str}", hub_a, 50000.0, now - timedelta(seconds=24), "UPI", dev),
        make_transaction(f"TXN-CMPA-{ts_str}-03", f"ACC-VIC-A3-{ts_str}", hub_a, 40000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-CMPA-{ts_str}-04", f"ACC-VIC-A4-{ts_str}", hub_a, 35000.0, now - timedelta(seconds=16), "UPI", dev),
        # Campaign Beta (Inflows to hub_b)
        make_transaction(f"TXN-CMPB-{ts_str}-01", f"ACC-VIC-B1-{ts_str}", hub_b, 35000.0, now - timedelta(seconds=12), "UPI", dev),
        make_transaction(f"TXN-CMPB-{ts_str}-02", f"ACC-VIC-B2-{ts_str}", hub_b, 40000.0, now - timedelta(seconds=8), "UPI", dev),
        # Outflow from Alpha to Cashout (98%)
        make_transaction(f"TXN-CMPA-{ts_str}-OUT", hub_a, cashout, 166000.0, now - timedelta(seconds=2), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="16 — Concurrent Dual-Campaign Blitz",
        transactions=txs,
        target_flagged_account=hub_a,
        api_url=api_url,
        account_metadata=accounts,
        dry_run=dry_run,
        speed=speed,
    )
    return success

if __name__ == "__main__":
    api_url, dry_run, speed = parse_cli_args()
    run(api_url=api_url, dry_run=dry_run, speed=speed)
