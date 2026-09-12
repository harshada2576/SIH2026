#!/usr/bin/env python3
"""
Scenario 19: Hardware Fingerprint Device-Sharing Syndicate
5 different bank accounts operate from the exact same mobile hardware fingerprint,
executing rapid layered transfers within seconds.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    shared_dev = f"DEV-IMEI-SYN-{ts_str}"
    m1 = f"ACC-DEV-M1-{ts_str}"
    m2 = f"ACC-DEV-M2-{ts_str}"
    aggr = f"ACC-DEV-AGGR-{ts_str}"
    cashout = f"ACC-DEV-CASH-{ts_str}"

    accounts = [
        make_account(m1, tier="mule_l1", age_days=1, terminals=["ATM-HDFC-Ce-001"], device=shared_dev),
        make_account(m2, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001"], device=shared_dev),
        make_account(aggr, tier="aggregator", age_days=1, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002", "ATM-ICICI-Ce-004"], device=shared_dev),
    ]

    txs = [
        make_transaction(f"TXN-DEV-{ts_str}-01", f"ACC-VIC-D1-{ts_str}", m1, 35000.0, now - timedelta(seconds=28), "UPI", shared_dev),
        make_transaction(f"TXN-DEV-{ts_str}-02", f"ACC-VIC-D2-{ts_str}", m2, 40000.0, now - timedelta(seconds=24), "UPI", shared_dev),
        make_transaction(f"TXN-DEV-{ts_str}-03", m1, aggr, 34000.0, now - timedelta(seconds=18), "UPI", shared_dev),
        make_transaction(f"TXN-DEV-{ts_str}-04", m2, aggr, 39000.0, now - timedelta(seconds=14), "UPI", shared_dev),
        make_transaction(f"TXN-DEV-{ts_str}-05", f"ACC-VIC-D3-{ts_str}", aggr, 45000.0, now - timedelta(seconds=10), "UPI", shared_dev),
        make_transaction(f"TXN-DEV-{ts_str}-06", f"ACC-VIC-D4-{ts_str}", aggr, 40000.0, now - timedelta(seconds=6), "UPI", shared_dev),
        make_transaction(f"TXN-DEV-{ts_str}-07", aggr, cashout, 154000.0, now - timedelta(seconds=2), "IMPS", shared_dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="19 — Hardware Fingerprint Syndicate Chain",
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
