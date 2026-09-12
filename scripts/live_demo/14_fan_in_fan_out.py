#!/usr/bin/env python3
"""
Scenario 14: Concentrator Fan-In / Fan-Out Clearing Hub
5 victim/feeder accounts dump funds simultaneously into a central aggregator (Fan-In),
which immediately disperses funds across 4 secondary mules (Fan-Out) within seconds.
"""
from datetime import datetime, timedelta, timezone
from scripts.live_demo.common import get_now_utc, make_account, make_transaction, publish_and_verify, parse_cli_args

def run(api_url: str = "http://127.0.0.1:5003", dry_run: bool = False, speed: float = 1.0) -> bool:
    now = get_now_utc()
    ts_str = now.strftime("%H%M%S")
    hub = f"ACC-HUB-FIFO-{ts_str}"
    dev = f"DEV-FIFO-RING-{ts_str}"

    accounts = [
        make_account(hub, tier="aggregator", age_days=3, terminals=["ATM-HDFC-Ce-001", "AEPS-BCR-002"], device=dev),
    ]

    txs = [
        # 5 Inflows (Fan-In)
        make_transaction(f"TXN-FIFO-{ts_str}-IN1", f"ACC-VIC-F1-{ts_str}", hub, 30000.0, now - timedelta(seconds=30), "UPI", dev),
        make_transaction(f"TXN-FIFO-{ts_str}-IN2", f"ACC-VIC-F2-{ts_str}", hub, 35000.0, now - timedelta(seconds=26), "UPI", dev),
        make_transaction(f"TXN-FIFO-{ts_str}-IN3", f"ACC-VIC-F3-{ts_str}", hub, 40000.0, now - timedelta(seconds=22), "UPI", dev),
        make_transaction(f"TXN-FIFO-{ts_str}-IN4", f"ACC-VIC-F4-{ts_str}", hub, 25000.0, now - timedelta(seconds=18), "UPI", dev),
        make_transaction(f"TXN-FIFO-{ts_str}-IN5", f"ACC-VIC-F5-{ts_str}", hub, 30000.0, now - timedelta(seconds=14), "UPI", dev),
        # 4 Outflows (Fan-Out)
        make_transaction(f"TXN-FIFO-{ts_str}-OUT1", hub, f"ACC-MULE-O1-{ts_str}", 38000.0, now - timedelta(seconds=8), "IMPS", dev),
        make_transaction(f"TXN-FIFO-{ts_str}-OUT2", hub, f"ACC-MULE-O2-{ts_str}", 39000.0, now - timedelta(seconds=6), "IMPS", dev),
        make_transaction(f"TXN-FIFO-{ts_str}-OUT3", hub, f"ACC-MULE-O3-{ts_str}", 39000.0, now - timedelta(seconds=4), "IMPS", dev),
        make_transaction(f"TXN-FIFO-{ts_str}-OUT4", hub, f"ACC-MULE-O4-{ts_str}", 40000.0, now - timedelta(seconds=1), "IMPS", dev),
    ]

    success, _ = publish_and_verify(
        scenario_name="14 — Concentrator Fan-In / Fan-Out Hub",
        transactions=txs,
        target_flagged_account=hub,
        api_url=api_url,
        account_metadata=accounts,
        dry_run=dry_run,
        speed=speed,
    )
    return success

if __name__ == "__main__":
    api_url, dry_run, speed = parse_cli_args()
    run(api_url=api_url, dry_run=dry_run, speed=speed)
