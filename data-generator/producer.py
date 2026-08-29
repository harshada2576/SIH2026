"""
data-generator/producer.py

Reads generated synthetic transactions from data/output/transactions.csv,
extracts the 7 locked transaction fields, keys each event by source_account_id
via pipeline/partition_strategy.py, and publishes them to Kafka topic "transactions".
"""

import csv
import json
import logging
import sys
import time
from pathlib import Path
from kafka import KafkaProducer

# Resolve repository paths
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from pipeline.partition_strategy import get_partition_key
except ImportError:
    from partition_strategy import get_partition_key

from shared.kafka_utils import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRANSACTIONS_TOPIC,
    get_kafka_producer,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("producer")

KAFKA_BOOTSTRAP = KAFKA_BOOTSTRAP_SERVERS
DEFAULT_CSV_PATH = REPO_ROOT / "data" / "output" / "transactions.csv"


def load_transactions_from_csv(csv_path: Path | str = DEFAULT_CSV_PATH) -> list[dict]:
    """
    Reads transactions.csv and normalizes records to the 7 locked transaction fields:
    - transaction_id: str
    - source_account_id: str
    - target_account_id: str
    - amount_inr: float
    - timestamp: str (ISO 8601)
    - payment_channel: str
    - device_fingerprint: str

    Ignores extra fields (balance_before, balance_after).
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Transactions CSV not found at: {path}")

    transactions = []
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx = {
                "transaction_id": str(row["transaction_id"]),
                "source_account_id": str(row["source_account_id"]),
                "target_account_id": str(row["target_account_id"]),
                "amount_inr": float(row["amount_inr"]),
                "timestamp": str(row["timestamp"]),
                "payment_channel": str(row.get("payment_channel", "UPI")),
                "device_fingerprint": str(row.get("device_fingerprint", "")),
            }
            transactions.append(tx)

    # Sort chronologically by timestamp so Kafka receives a natural time-ordered stream
    transactions.sort(key=lambda tx: tx["timestamp"])
    return transactions


def publish_transactions(
    transactions: list[dict],
    bootstrap_servers: str = KAFKA_BOOTSTRAP,
    topic: str = TRANSACTIONS_TOPIC,
    events_per_sec: float = 100.0,
):
    """
    Publishes transaction events to Kafka topic "transactions",
    keyed by partition_strategy.get_partition_key(tx).
    """
    producer = get_kafka_producer(
        bootstrap_servers=bootstrap_servers,
    )

    log.info(f"Starting publication of {len(transactions)} transactions to '{topic}'...")
    delay = (1.0 / events_per_sec) if events_per_sec > 0 else 0.0

    count = 0
    for tx in transactions:
        key = get_partition_key(tx)
        producer.send(topic, key=key, value=tx)
        count += 1
        if delay > 0:
            time.sleep(delay)

    producer.flush()
    log.info(f"Finished publishing {count} transactions.")


def run(csv_path: Path | str = DEFAULT_CSV_PATH, events_per_sec: float = 100.0):
    txs = load_transactions_from_csv(csv_path)
    publish_transactions(txs, events_per_sec=events_per_sec)


if __name__ == "__main__":
    run()
