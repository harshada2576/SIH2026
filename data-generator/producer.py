#!/usr/bin/env python3
"""
data-generator/producer.py — Publishes generated transactions to the Kafka 'transactions' topic
SIH26184 — Predictive Cash Egress Interception — Workstream 1

Reads generated transactions (from data-generator/data/transactions.csv or data/output/transactions.csv)
and publishes each row as a JSON event to Kafka, matching the LOCKED schema in Architecture.md §6.1
exactly — 7 fields, keyed by source_account_id partition strategy.

Supports running standalone:
    python data-generator/producer.py
or from within data-generator directory:
    python producer.py
"""

import csv
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Resolve repository paths
REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DIR = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

try:
    import config
except ImportError:
    config = None

try:
    from pipeline.partition_strategy import get_partition_key
except ImportError:
    def get_partition_key(tx: dict) -> str:
        src = tx.get("source_account_id", "")
        return hashlib.md5(src.encode("utf-8")).hexdigest()[:8]

try:
    from shared.kafka_utils import (
        KAFKA_BOOTSTRAP_SERVERS,
        TRANSACTIONS_TOPIC,
        get_kafka_producer,
    )
except ImportError:
    KAFKA_BOOTSTRAP_SERVERS = getattr(config, "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    TRANSACTIONS_TOPIC = getattr(config, "KAFKA_TRANSACTIONS_TOPIC", "transactions")
    get_kafka_producer = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("producer")

# 7 locked fields per Architecture.md §6.1
LOCKED_KAFKA_FIELDS = [
    "transaction_id",
    "source_account_id",
    "target_account_id",
    "amount_inr",
    "timestamp",
    "payment_channel",
    "device_fingerprint",
]


def resolve_default_csv_path() -> Path:
    """Find the default transactions CSV file across modular and legacy paths."""
    candidates = [
        MODULE_DIR / "data" / "transactions.csv",
        REPO_ROOT / "data" / "output" / "transactions.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def to_kafka_event(row: dict) -> dict:
    """Strip a transaction row down to EXACTLY the 7 locked Kafka fields."""
    return {
        "transaction_id": str(row.get("transaction_id", "")),
        "source_account_id": str(row.get("source_account_id", "")),
        "target_account_id": str(row.get("target_account_id", "")),
        "amount_inr": float(row.get("amount_inr", 0.0)),
        "timestamp": str(row.get("timestamp", "")),
        "payment_channel": str(row.get("payment_channel", "UPI")),
        "device_fingerprint": str(row.get("device_fingerprint", "")),
    }


def load_transactions_from_csv(csv_path: Path | str = None) -> list[dict]:
    """
    Reads transactions CSV, normalizes records to the 7 locked fields,
    and returns them sorted chronologically by timestamp.
    """
    path = Path(csv_path) if csv_path else resolve_default_csv_path()
    if not path.exists():
        raise FileNotFoundError(f"Transactions CSV not found at: {path}")

    transactions = []
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx = to_kafka_event(row)
            transactions.append(tx)

    # Sort chronologically by timestamp for natural stream replay
    transactions.sort(key=lambda tx: tx["timestamp"])
    return transactions


def build_producer(bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS):
    """Create and return a KafkaProducer with graceful failure reporting."""
    if get_kafka_producer is not None:
        return get_kafka_producer(bootstrap_servers=bootstrap_servers)

    try:
        from kafka import KafkaProducer
    except ModuleNotFoundError as e:
        log.error(f"Kafka client not found: {e}. Install via: pip install -r requirements.txt")
        sys.exit(1)

    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
        request_timeout_ms=10000,
    )


def publish_transactions(
    transactions: list[dict],
    bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
    topic: str = TRANSACTIONS_TOPIC,
    events_per_sec: float = 100.0,
) -> tuple[int, int]:
    """
    Publishes transaction events to Kafka topic, keyed by partition strategy.
    Returns (sent_count, failed_count).
    """
    producer = build_producer(bootstrap_servers=bootstrap_servers)
    log.info(f"Publishing {len(transactions)} transactions to '{topic}' at ~{events_per_sec} evt/s...")

    delay = (1.0 / events_per_sec) if events_per_sec > 0 else 0.0
    sent, failed = 0, 0

    for tx in transactions:
        event = to_kafka_event(tx)
        key = get_partition_key(event)
        try:
            producer.send(topic, key=key, value=event)
            sent += 1
        except Exception as e:
            log.warning(f"Failed to publish transaction {event.get('transaction_id')}: {e}")
            failed += 1

        if delay > 0:
            time.sleep(delay)

    producer.flush()
    try:
        producer.close()
    except Exception:
        pass

    log.info(f"Publication complete. Sent: {sent}, Failed: {failed}")
    return sent, failed


def run(csv_path: Path | str = None, events_per_sec: float = 100.0) -> tuple[int, int]:
    """Entrypoint function for pipeline/scripts invocation."""
    txs = load_transactions_from_csv(csv_path)
    return publish_transactions(txs, events_per_sec=events_per_sec)


def main():
    """CLI entrypoint."""
    csv_file = resolve_default_csv_path()
    rate = getattr(config, "KAFKA_EVENTS_PER_SECOND", 100) if config else 100
    if not csv_file.exists():
        log.error(f"No transactions file found at {csv_file}. Please run generate.py first.")
        sys.exit(1)
    run(csv_path=csv_file, events_per_sec=rate)


if __name__ == "__main__":
    main()
