#!/usr/bin/env python3
"""
Scenario 02: Layering Chain
A stolen ₹1,60,000 transfer passes rapidly through a 4-hop mule chain:
Victim -> Mule L1 -> Mule L2 -> Mule L3 -> Aggregator -> Cash-out Terminal
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    vic = f"ACC-VIC-LAY-{ts_str}"
    m1 = f"ACC-M1-LAY-{ts_str}"
    m2 = f"ACC-M2-LAY-{ts_str}"
    m3 = f"ACC-M3-LAY-{ts_str}"
    aggr = f"ACC-AGGR-LAY-{ts_str}"
    cashout = f"ACC-CASH-LAY-{ts_str}"
    dev = f"DEV-LAY-RING-{ts_str}"

    accounts = [
        make_account(m1, tier="mule_l1", age_days=3, terminals=["ATM-ICICI-Ce-004"], kyc_id="KYC-LAY-RING-01", device=dev),
        make_account(m2, tier="mule_l2", age_days=4, terminals=["ATM-ICICI-Ce-004"], kyc_id="KYC-LAY-RING-01", device=dev),
        make_account(m3, tier="mule_l2", age_days=5, terminals=["ATM-ICICI-Ce-004"], kyc_id="KYC-LAY-RING-01", device=dev),
        make_account(aggr, tier="aggregator", age_days=2, terminals=["ATM-ICICI-Ce-004", "ATM-HDFC-Ce-001"], kyc_id="KYC-LAY-RING-01", device=dev),
    ]

    txs = [
        make_transaction(f"TXN-LAY-{ts_str}-01", vic, m1, 160000.0, now - timedelta(seconds=40), "IMPS", dev),
        make_transaction(f"TXN-LAY-{ts_str}-02", m1, m2, 155000.0, now - timedelta(seconds=30), "UPI", dev),
        make_transaction(f"TXN-LAY-{ts_str}-03", m2, m3, 150000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-LAY-{ts_str}-04", m3, aggr, 146000.0, now - timedelta(seconds=10), "UPI", dev),
        make_transaction(f"TXN-LAY-{ts_str}-05", f"ACC-FEED-LAY-{ts_str}", aggr, 30000.0, now - timedelta(seconds=6), "UPI", dev),
        make_transaction(f"TXN-LAY-{ts_str}-06", aggr, cashout, 172000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="02 — Multi-Hop Layering Chain",
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
