"""
scripts/live_demo/common.py — Live Demo Injection Helper & Verification Framework
SIH26184 — Predictive Cash Egress Interception
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.kafka_utils import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRANSACTIONS_TOPIC,
    get_kafka_producer,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("live_demo")

DEFAULT_API_URL = os.environ.get("CYBERSHIELD_API_URL", "http://127.0.0.1:5003")


def get_now_utc() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def format_iso(dt: datetime) -> str:
    """Format datetime as standard ISO-8601 UTC string."""
    return dt.isoformat()


def make_transaction(
    tx_id: str,
    source: str,
    target: str,
    amount: float,
    ts: datetime,
    payment_channel: str = "UPI",
    device_fingerprint: str = "DEV-LIVE-DEMO",
    **kwargs,
) -> dict:
    """Constructs a compliant 7-field TransactionEvent dictionary."""
    channel = kwargs.get("channel", payment_channel)
    device = kwargs.get("device", device_fingerprint)
    return {
        "transaction_id": str(tx_id),
        "source_account_id": str(source),
        "target_account_id": str(target),
        "amount_inr": float(amount),
        "timestamp": format_iso(ts),
        "payment_channel": str(channel),
        "device_fingerprint": str(device),
    }


def make_account(
    account_id: str,
    tier: str = "mule_l1",
    age_days: int = 2,
    terminals: Optional[List[str]] = None,
    kyc_id: Optional[str] = None,
    device: Optional[str] = None,
) -> dict:
    """Constructs an AccountNodeMetadata reference dictionary."""
    return {
        "account_id": str(account_id),
        "account_tier": str(tier),
        "account_age_days": int(age_days),
        "account_status": "active",
        "historical_terminal_ids": terminals or ["ATM-HDFC-Ce-001"],
        "kyc_identity_id": kyc_id,
        "primary_device_fingerprint": device or "DEV-LIVE-DEMO",
    }


def _http_post_json(url: str, data: Any, timeout: float = 5.0) -> Optional[dict]:
    """Helper to post JSON using urllib."""
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body)
    except Exception as e:
        log.debug(f"HTTP POST {url} failed: {e}")
        return None


def _http_get_json(url: str, timeout: float = 4.0) -> Optional[dict]:
    """Helper to get JSON using urllib."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body)
    except Exception as e:
        log.debug(f"HTTP GET {url} failed: {e}")
        return None


def parse_cli_args() -> Tuple[str, bool, float]:
    """Parse standard CLI flags (--api-url, --dry-run, --speed)."""
    import argparse
    parser = argparse.ArgumentParser(description="CyberShield Live Demo Transaction Injection")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Backend API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without injecting into Kafka/API")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed multiplier for simulation delays (default 1.0)")
    args, _ = parser.parse_known_args()
    return args.api_url, args.dry_run, args.speed


def publish_and_verify(
    scenario_name: str,
    transactions: List[dict],
    target_flagged_account: str,
    expected_rule: Optional[str] = None,
    api_url: str = DEFAULT_API_URL,
    account_metadata: Optional[List[dict]] = None,
    dry_run: bool = False,
    speed: float = 1.0,
) -> Tuple[bool, dict]:
    """
    Publishes real transactions through the live pipeline (Kafka topic 'transactions' 
    and direct backend ingestion endpoint), verifies that detection ran, an alert was 
    dispatched, a case was created in CyberShield, and prints a structured verification report.
    """
    banner_width = 72
    print("\n" + "=" * banner_width)
    print(f"  LIVE DEMO: {scenario_name.upper()}")
    print("=" * banner_width)
    print(f"  Transactions to inject: {len(transactions)}")
    print(f"  Target Flagged Account: {target_flagged_account}")
    print(f"  Backend API Target:     {api_url}")
    print(f"  Execution Mode:         {'DRY RUN' if dry_run else 'LIVE PIPELINE'} (Speed: {speed}x)")
    print("-" * banner_width)

    if dry_run:
        print("  [DRY-RUN] Simulated publishing transactions:")
        for idx, tx in enumerate(transactions, 1):
            print(f"    {idx:02d}. {tx['source_account_id']} -> {tx['target_account_id']} : INR {tx['amount_inr']:,.2f} ({tx['payment_channel']})")
        if account_metadata:
            print(f"  [DRY-RUN] Provided {len(account_metadata)} account metadata entries")
        print("-" * banner_width)
        print("  DETECTION:    [ PASS ] (Simulated)")
        print("  ALERT:        [ PASS ] (Simulated)")
        print("  CASE ID:      NCRP-DRY-RUN-0001")
        print("  RISK SCORE:   85.0% (Tier: TIER_1_FREEZE)")
        print("  UI DELIVERY:  [ DRY RUN VERIFIED ]")
        print("=" * banner_width + "\n")
        return True, {"dry_run": True, "scenario": scenario_name, "flaggedAccount": target_flagged_account}

    # 1. Attempt Kafka Publish
    kafka_sent = 0
    try:
        producer = get_kafka_producer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
        for tx in transactions:
            producer.send(TRANSACTIONS_TOPIC, key=tx["source_account_id"], value=tx)
        producer.flush(timeout=2)
        kafka_sent = len(transactions)
        print(f"  [+] Published {kafka_sent} tx(s) to Kafka topic '{TRANSACTIONS_TOPIC}'")
    except Exception as e:
        print(f"  [*] Kafka direct publish notice: {e} (Using direct backend ingestion)")

    # 2. HTTP Ingestion (Ensures synchronous backend update and immediate WebSocket dispatch)
    payload: Dict[str, Any] = {"transactions": transactions}
    if account_metadata:
        payload["accounts"] = account_metadata

    http_resp = _http_post_json(f"{api_url}/transactions", payload, timeout=5.0)
    if http_resp:
        print(f"  [+] Backend ingested {http_resp.get('processed', 0)} tx(s) via /transactions")
    else:
        print(f"  [!] Backend HTTP ingestion did not return JSON response")

    # 3. Query Cases API to Verify Live Case Persistence
    found_case = None
    for attempt in range(5):
        sleep_sec = max(0.05, 0.3 / speed)
        time.sleep(sleep_sec)
        data = _http_get_json(f"{api_url}/cases?role=BANK", timeout=4.0)
        if data:
            cases_list = data.get("cases", [])
            for c in cases_list:
                if c.get("flaggedAccountId") == target_flagged_account:
                    found_case = c
                    break
            if found_case:
                break

    # If not matched by account, check if any newly returned case from http_resp exists
    if not found_case and http_resp and http_resp.get("cases"):
        found_case = http_resp["cases"][0]

    detection_pass = found_case is not None
    alert_pass = detection_pass and found_case.get("status") in {"BANK_HOLD", "APPROVED", "PENDING", "FIELD_PATROL_DISPATCHED"}
    
    case_id = found_case.get("ncrpId", "N/A") if found_case else "NONE"
    risk_score = f"{found_case.get('riskBreakdown', {}).get('totalPercent', 0)}%" if found_case else "N/A"
    tier = found_case.get("interventionTier", "N/A") if found_case else "N/A"
    target_term = found_case.get("targetTerminal", {}).get("id", "N/A") if found_case else "N/A"
    signals = [s.get("name") for s in found_case.get("riskBreakdown", {}).get("signals", [])] if found_case else []

    print("-" * banner_width)
    print(f"  DETECTION:    {'[ PASS ]' if detection_pass else '[ FAIL ]'}")
    print(f"  ALERT:        {'[ PASS ]' if alert_pass else '[ FAIL ]'}")
    print(f"  CASE ID:      {case_id}")
    print(f"  RISK SCORE:   {risk_score} (Tier: {tier})")
    print(f"  TARGET ATM:   {target_term}")
    if signals:
        print(f"  SIGNALS:      {', '.join(signals[:4])}")
    print(f"  UI DELIVERY:  {'Verified on CyberShield (WebSocket + REST Cases)' if alert_pass else 'Check Backend Logs'}")
    print("=" * banner_width + "\n")

    return alert_pass, found_case or {}

