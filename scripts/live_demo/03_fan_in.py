#!/usr/bin/env python3
"""
Scenario 03: Multi-Source Fan-In Consolidation
Multiple victim feeder accounts converge simultaneously onto an aggregator mule.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    aggr = f"ACC-AGGR-FANIN-{ts_str}"
    cashout = f"ACC-CASH-FANIN-{ts_str}"
    dev = f"DEV-FANIN-RING-{ts_str}"

    accounts = [
        make_account(aggr, tier="aggregator", age_days=2, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-FIN-{ts_str}-01", f"ACC-VIC-01-{ts_str}", aggr, 35000.0, now - timedelta(seconds=24), "UPI", dev),
        make_transaction(f"TXN-FIN-{ts_str}-02", f"ACC-VIC-02-{ts_str}", aggr, 40000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-FIN-{ts_str}-03", f"ACC-VIC-03-{ts_str}", aggr, 32000.0, now - timedelta(seconds=16), "UPI", dev),
        make_transaction(f"TXN-FIN-{ts_str}-04", f"ACC-VIC-04-{ts_str}", aggr, 38000.0, now - timedelta(seconds=12), "UPI", dev),
        make_transaction(f"TXN-FIN-{ts_str}-05", f"ACC-VIC-05-{ts_str}", aggr, 25000.0, now - timedelta(seconds=8), "UPI", dev),
        make_transaction(f"TXN-FIN-{ts_str}-06", aggr, cashout, 165000.0, now - timedelta(seconds=2), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="03 — Multi-Source Fan-In Consolidation",
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
