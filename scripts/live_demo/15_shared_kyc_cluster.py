#!/usr/bin/env python3
"""
Scenario 15: Shared KYC Identity Syndicate
4 distinct mule accounts created with the same fraudulent KYC document (Aadhaar/PAN hash)
simultaneously pool victim funds into a common clearing account.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    kyc_id = f"KYC-SYN-DOC-{ts_str}"
    aggr = f"ACC-KYC-AGGR-{ts_str}"
    m1 = f"ACC-KYC-M1-{ts_str}"
    m2 = f"ACC-KYC-M2-{ts_str}"
    m3 = f"ACC-KYC-M3-{ts_str}"
    m4 = f"ACC-KYC-M4-{ts_str}"
    cashout = f"ACC-KYC-CASH-{ts_str}"
    dev = f"DEV-KYC-RING-{ts_str}"

    accounts = [
        make_account(m1, tier="mule_l1", age_days=2, kyc_id=kyc_id, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(m2, tier="mule_l1", age_days=2, kyc_id=kyc_id, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(m3, tier="mule_l1", age_days=3, kyc_id=kyc_id, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(m4, tier="mule_l1", age_days=3, kyc_id=kyc_id, terminals=["ATM-HDFC-Ce-001"], device=dev),
        make_account(aggr, tier="aggregator", age_days=1, kyc_id=kyc_id, terminals=["ATM-HDFC-Ce-001"], device=dev),
    ]

    txs = [
        make_transaction(f"TXN-KYC-{ts_str}-01", m1, aggr, 35000.0, now - timedelta(seconds=25), "UPI", dev),
        make_transaction(f"TXN-KYC-{ts_str}-02", m2, aggr, 40000.0, now - timedelta(seconds=20), "UPI", dev),
        make_transaction(f"TXN-KYC-{ts_str}-03", m3, aggr, 38000.0, now - timedelta(seconds=15), "UPI", dev),
        make_transaction(f"TXN-KYC-{ts_str}-04", m4, aggr, 42000.0, now - timedelta(seconds=10), "UPI", dev),
        make_transaction(f"TXN-KYC-{ts_str}-05", aggr, cashout, 150000.0, now - timedelta(seconds=2), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="15 — Shared KYC Identity Syndicate",
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
