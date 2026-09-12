#!/usr/bin/env python3
"""
Scenario 20: Layering Chain with Distributed Multi-Terminal Cashout
A stolen fund is layered across 3 consecutive hops and then immediately split into
3 separate cashout destination accounts targeting nearby ATMs.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    vic = f"ACC-VIC-LDC-{ts_str}"
    m1 = f"ACC-M1-LDC-{ts_str}"
    m2 = f"ACC-M2-LDC-{ts_str}"
    aggr = f"ACC-AGGR-LDC-{ts_str}"
    dev = f"DEV-LDC-RING-{ts_str}"

    accounts = [
        make_account(m1, tier="mule_l1", age_days=2, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(m2, tier="mule_l2", age_days=3, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(aggr, tier="aggregator", age_days=1, terminals=["ATM-HDFC-Ce-001", "ATM-ICICI-Ce-004", "AEPS-BCR-002"], device=dev),
    ]

    txs = [
        # Hop 1: Victim -> Mule 1
        make_transaction(f"TXN-LDC-{ts_str}-01", vic, m1, 150000.0, now - timedelta(seconds=35), "IMPS", dev),
        # Hop 2: Mule 1 -> Mule 2
        make_transaction(f"TXN-LDC-{ts_str}-02", m1, m2, 146000.0, now - timedelta(seconds=26), "UPI", dev),
        # Hop 3: Mule 2 -> Aggregator
        make_transaction(f"TXN-LDC-{ts_str}-03", m2, aggr, 142000.0, now - timedelta(seconds=18), "UPI", dev),
        # Fan-in boost
        make_transaction(f"TXN-LDC-{ts_str}-04", f"ACC-VIC2-LDC-{ts_str}", aggr, 30000.0, now - timedelta(seconds=12), "UPI", dev),
        # 3-Way Cashout Split
        make_transaction(f"TXN-LDC-{ts_str}-05", aggr, f"ACC-CASH-A-{ts_str}", 55000.0, now - timedelta(seconds=6), "UPI", dev),
        make_transaction(f"TXN-LDC-{ts_str}-06", aggr, f"ACC-CASH-B-{ts_str}", 55000.0, now - timedelta(seconds=4), "UPI", dev),
        make_transaction(f"TXN-LDC-{ts_str}-07", aggr, f"ACC-CASH-C-{ts_str}", 58000.0, now - timedelta(seconds=1), "UPI", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="20 — Layering with Distributed Cashout Split",
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
