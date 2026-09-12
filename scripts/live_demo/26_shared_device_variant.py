#!/usr/bin/env python3
"""
Scenario 26: 6-Account Shared Hardware Cluster Syndicate Variant
6 distinct mule accounts operating from a single rooted mobile handset.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    dev = f"DEV-ROOTED-SYN-{ts_str}"
    m1 = f"ACC-CLU-M1-{ts_str}"
    m2 = f"ACC-CLU-M2-{ts_str}"
    aggr = f"ACC-CLU-AGGR-{ts_str}"
    cashout = f"ACC-CLU-CASH-{ts_str}"

    accounts = [
        make_account(m1, tier="mule_l1", age_days=1, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(m2, tier="mule_l1", age_days=1, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(aggr, tier="aggregator", age_days=1, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-V26-{ts_str}-01", f"ACC-VIC-1-{ts_str}", m1, 30000.0, now - timedelta(seconds=24), "UPI", dev),
        make_transaction(f"TXN-V26-{ts_str}-02", f"ACC-VIC-2-{ts_str}", m2, 35000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-V26-{ts_str}-03", m1, aggr, 29000.0, now - timedelta(seconds=15), "UPI", dev),
        make_transaction(f"TXN-V26-{ts_str}-04", m2, aggr, 34000.0, now - timedelta(seconds=11), "UPI", dev),
        make_transaction(f"TXN-V26-{ts_str}-05", f"ACC-VIC-3-{ts_str}", aggr, 40000.0, now - timedelta(seconds=7), "UPI", dev),
        make_transaction(f"TXN-V26-{ts_str}-06", f"ACC-VIC-4-{ts_str}", aggr, 35000.0, now - timedelta(seconds=4), "UPI", dev),
        make_transaction(f"TXN-V26-{ts_str}-07", aggr, cashout, 135000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="26 — Shared Hardware Cluster Variant",
        transactions=txs,
        target_flagged_account=aggr,
        api_url=api_url,
        account_metadata=accounts,
        dry_run=dry_run,
        speed=speed,
    )
    return success

if __name__ == "__main__":
    api_url, dry_run, speed = parse_cli_args()
    run(api_url=api_url, dry_run=dry_run, speed=speed)
