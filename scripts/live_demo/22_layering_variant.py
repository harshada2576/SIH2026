#!/usr/bin/env python3
"""
Scenario 22: Deep 5-Hop Layering Chain Variant
Extended layering scenario spanning 5 intermediate mule hops across multiple payment channels.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    vic = f"ACC-VIC-V22-{ts_str}"
    m1 = f"ACC-M1-V22-{ts_str}"
    m2 = f"ACC-M2-V22-{ts_str}"
    m3 = f"ACC-M3-V22-{ts_str}"
    m4 = f"ACC-M4-V22-{ts_str}"
    aggr = f"ACC-AGGR-V22-{ts_str}"
    cashout = f"ACC-CASH-V22-{ts_str}"
    dev = f"DEV-V22-RING-{ts_str}"

    accounts = [
        make_account(m1, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(m2, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(m3, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(m4, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(aggr, tier="aggregator", age_days=1, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-V22-{ts_str}-01", vic, m1, 180000.0, now - timedelta(seconds=45), "IMPS", dev),
        make_transaction(f"TXN-V22-{ts_str}-02", m1, m2, 175000.0, now - timedelta(seconds=36), "UPI", dev),
        make_transaction(f"TXN-V22-{ts_str}-03", m2, m3, 170000.0, now - timedelta(seconds=27), "UPI", dev),
        make_transaction(f"TXN-V22-{ts_str}-04", m3, m4, 166000.0, now - timedelta(seconds=18), "UPI", dev),
        make_transaction(f"TXN-V22-{ts_str}-05", m4, aggr, 162000.0, now - timedelta(seconds=9), "UPI", dev),
        make_transaction(f"TXN-V22-{ts_str}-06", aggr, cashout, 160000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="22 — Deep 5-Hop Layering Chain Variant",
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
