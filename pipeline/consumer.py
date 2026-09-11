"""
pipeline/consumer.py

Reads raw transaction events from the "transactions" Kafka topic, updates the
live GraphStore, and publishes lightweight structural signals to a new
"graph_signals" topic for the detection/scorer workstream to consume.

NOTE ON THE NEW TOPIC: "graph_signals" is not in the original Architecture.md
contract. Proposed schema below — confirm with the detection team before they
build against it, per Rules.md.

Proposed graph_signals event:
{
  "account_id": "ACC001",
  "timestamp": "2026-08-29T10:03:21",
  "fan_in_count": 4,
  "fan_out_count": 0,
  "distinct_counterparties": 4,
  "shared_device_accounts": ["ACC002", "ACC003"],
  "account_tier": "aggregator",
  "chain_depth": 3,
  "historical_terminal_ids": ["ATM007"]
}

Adjust import paths below (kafka_utils, schemas) to match whatever
shared/kafka_utils.py and shared/schemas.py actually expose once merged —
this file assumes reasonable helper function names as placeholders.
"""

import csv
import json
import logging
import signal
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from graph_store import GraphStore
except ImportError:
    from pipeline.graph_store import GraphStore

from shared.kafka_utils import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRANSACTIONS_TOPIC,
    GRAPH_SIGNALS_TOPIC,
    GRAPH_BUILDER_GROUP,
    get_kafka_consumer,
    get_kafka_producer,
    safe_json_deserializer,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("consumer")

DEFAULT_ACCOUNTS_PATH = REPO_ROOT / "data" / "output" / "accounts.csv"
DEFAULT_TERMINALS_PATH = REPO_ROOT / "data" / "output" / "terminals.csv"

KAFKA_BOOTSTRAP = KAFKA_BOOTSTRAP_SERVERS
SIGNALS_TOPIC = GRAPH_SIGNALS_TOPIC

FAN_ALERT_THRESHOLD = 3  # emit a signal-worth-watching once an account sees >= this many
                          # in-window in/out edges; tune once real synthetic data is in


def _deserialize_transaction(raw_bytes: bytes | str | None) -> dict | None:
    """
    Safely decodes transaction JSON. Returns None on malformed poison-pill payloads
    to prevent consumer process crashes.
    """
    return safe_json_deserializer(raw_bytes)


def build_signal(store: GraphStore, account_id: str, ts) -> dict:
    return {
        "account_id": account_id,
        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        "fan_in_count": store.fan_in_count(account_id),
        "fan_out_count": store.fan_out_count(account_id),
        "distinct_counterparties": len(store.distinct_counterparties_in_window(account_id)),
        "shared_device_accounts": store.shares_device_fingerprint(account_id),
        "chain_depth": store.account_chain_depth(account_id),
        "historical_terminal_ids": store.historical_terminal_affinity(account_id),
    }


def process_transaction(store: GraphStore, tx: dict) -> list[dict]:
    """
    Safely processes a single transaction event against GraphStore.
    Returns a list of generated graph signals for source and target accounts,
    or an empty list if malformed/duplicate.
    """
    if not isinstance(tx, dict):
        log.warning(f"Skipping non-dict transaction payload: {type(tx)}")
        return []

    required = ("transaction_id", "source_account_id", "target_account_id", "amount_inr", "timestamp")
    for f in required:
        if f not in tx:
            log.warning(f"Skipping malformed transaction, missing '{f}': {tx}")
            return []

    try:
        accepted = store.add_transaction(tx)
        if not accepted:
            log.debug(f"Duplicate transaction ignored: {tx.get('transaction_id')}")
            return []
    except Exception as e:
        log.warning(f"Error updating GraphStore for transaction {tx.get('transaction_id')}: {e}")
        return []

    signals = []
    for account_id in (tx["source_account_id"], tx["target_account_id"]):
        sig = build_signal(store, account_id, tx["timestamp"])
        signals.append(sig)
    return signals


def load_reference_data(store: GraphStore, accounts_path: str | Path | None = None, terminals_path: str | Path | None = None):
    """
    Loads static Accounts and Terminals datasets from CSV once at startup.
    Normalizes types (int, float, list[str]) for graph store and downstream lookups.
    """
    accounts_file = Path(accounts_path) if accounts_path else DEFAULT_ACCOUNTS_PATH
    terminals_file = Path(terminals_path) if terminals_path else DEFAULT_TERMINALS_PATH

    accounts = []
    with open(accounts_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_terms = row.get("historical_terminal_ids", "")
            historical_terminal_ids = [t.strip() for t in raw_terms.split(",") if t.strip()]
            accounts.append({
                "account_id": row["account_id"],
                "account_tier": row.get("account_tier", "unknown"),
                "account_age_days": int(row.get("account_age_days", 0)),
                "account_status": row.get("account_status", "active"),
                "historical_terminal_ids": historical_terminal_ids,
                "primary_device_fingerprint": row.get("primary_device_fingerprint", ""),
                "account_region": row.get("account_region", ""),
            })

    terminals = []
    with open(terminals_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            terminals.append({
                "terminal_id": row["terminal_id"],
                "terminal_type": row.get("terminal_type", "ATM_KIOSK"),
                "latitude": float(row.get("latitude", 0.0)),
                "longitude": float(row.get("longitude", 0.0)),
                "district": row.get("district", ""),
                "pincode": row.get("pincode", ""),
                "status": row.get("status", "active"),
            })

    store.load_accounts(accounts)
    store.load_terminals(terminals)
    log.info(f"Loaded {len(accounts)} accounts from {accounts_file} and {len(terminals)} terminals from {terminals_file}")


def run(accounts_path: str | Path | None = None,
        terminals_path: str | Path | None = None):

    store = GraphStore(fan_window_seconds=300)
    load_reference_data(store, accounts_path, terminals_path)

    consumer = get_kafka_consumer(
        TRANSACTIONS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_deserializer=_deserialize_transaction,
        auto_offset_reset="earliest",
        group_id=GRAPH_BUILDER_GROUP,
        consumer_timeout_ms=1000,
    )

    producer = get_kafka_producer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
    )

    running = True

    def _signal_handler(signum, frame):
        nonlocal running
        log.info(f"Shutdown signal ({signum}) received. Initiating graceful shutdown...")
        running = False

    # Register OS signal handlers for graceful exit
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    log.info("Consumer started, listening for transactions...")

    try:
        while running:
            for message in consumer:
                if not running:
                    break
                tx = message.value
                if tx is None:
                    continue  # Poison pill skipped

                signals = process_transaction(store, tx)
                for signal_payload in signals:
                    producer.send(SIGNALS_TOPIC, value=signal_payload)

                    if signal_payload["fan_in_count"] >= FAN_ALERT_THRESHOLD or signal_payload["fan_out_count"] >= FAN_ALERT_THRESHOLD:
                        log.info(f"Elevated activity: {signal_payload['account_id']} -> {signal_payload}")
    except Exception as e:
        log.error(f"Unexpected error in consumer loop: {e}", exc_info=True)
    finally:
        log.info("Closing Kafka producer and consumer resources...")
        try:
            producer.flush(timeout=5)
            producer.close(timeout=5)
        except Exception as e:
            log.warning(f"Error closing producer: {e}")
        try:
            consumer.close(autocommit=True)
        except Exception as e:
            log.warning(f"Error closing consumer: {e}")
        log.info("Consumer shutdown complete.")


if __name__ == "__main__":
    try:
        run()
    except ConnectionError as e:
        print(f"\n[!] {e}\n")
        sys.exit(0)

