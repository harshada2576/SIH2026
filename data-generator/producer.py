#!/usr/bin/env python3
"""
producer.py — Publishes generated transactions to the Kafka 'transactions' topic
SIH26184 — Predictive Cash Egress Interception — Workstream 1

Reads data/transactions.csv (produced by generate.py) and publishes each row
as a JSON event to Kafka, matching the LOCKED schema in Architecture.md §6.1
exactly — 7 fields, nothing more.

CHANGELOG (this revision):
  - transactions.csv now carries balance_before/balance_after for ML
    purposes. This file explicitly filters the outgoing event down to only
    config.KAFKA_EVENT_FIELDS before publishing, so those two columns can
    NEVER leak into the Kafka event even if the CSV format changes again later.
  - Events are now sent in TRUE CHRONOLOGICAL (timestamp) order, regardless
    of the CSV's row order (which generate.py shuffles for dataset variety —
    see update request §14: "Kafka events should be sent according to
    chronological timestamp order so the real-time demo makes sense").

Uses `kafka-python-ng` (a maintained fork — see requirements.txt for why
plain `kafka-python` is broken on Python 3.12+).

Run standalone (Kafka must be running via docker-compose up first):

    python producer.py
"""

import csv
import hashlib
import json
import sys
import time
from datetime import datetime

import config


def build_producer():
    """Create and return a KafkaProducer, or exit cleanly with a clear message if Kafka is unreachable."""
    try:
        from kafka import KafkaProducer
    except ModuleNotFoundError as e:
        if "kafka" in str(e) and "vendor" in str(e):
            print("ERROR: kafka-python failed to import due to a known Python 3.12+ "
                  "compatibility bug (kafka.vendor.six.moves). See README.md "
                  "'Troubleshooting' section for the fix.", file=sys.stderr)
        else:
            print("ERROR: kafka client library not installed. Run: pip install -r requirements.txt",
                  file=sys.stderr)
        sys.exit(1)

    try:
        return KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k is not None else None,
            request_timeout_ms=10000,
        )
    except Exception as e:
        print(f"ERROR: could not connect to Kafka at {config.KAFKA_BOOTSTRAP_SERVERS}: {e}",
              file=sys.stderr)
        print("Is Kafka running? Try: docker compose up -d", file=sys.stderr)
        sys.exit(1)


def partition_key(event: dict) -> str:
    """Compute the partition key for an event, per config.KAFKA_PARTITION_KEY_STRATEGY."""
    return hashlib.md5(event["source_account_id"].encode()).hexdigest()[:8]


def to_kafka_event(row: dict) -> dict:
    """Strip a transactions.csv row down to EXACTLY the 7 locked Kafka fields.

    This is the enforcement point for the locked contract — even if
    transactions.csv grows more supporting columns in the future (it already
    has balance_before/balance_after), this function guarantees only the 7
    approved fields ever get published.
    """
    return {field: row[field] for field in config.KAFKA_EVENT_FIELDS}


def load_transactions_chronological(csv_path: str) -> list[dict]:
    """Load transactions.csv and return rows sorted by timestamp (oldest first)."""
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["amount_inr"] = float(row["amount_inr"])
            row["_ts"] = datetime.strptime(row["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
            rows.append(row)
    rows.sort(key=lambda r: r["_ts"])
    return rows


def main():
    events = load_transactions_chronological(config.TRANSACTIONS_CSV)
    if not events:
        print("No transactions found — run generate.py first.", file=sys.stderr)
        sys.exit(1)

    producer = build_producer()
    delay = 1.0 / config.KAFKA_EVENTS_PER_SECOND if config.KAFKA_EVENTS_PER_SECOND > 0 else 0

    print(f"Publishing {len(events)} events to topic '{config.KAFKA_TRANSACTIONS_TOPIC}' "
          f"in chronological order at ~{config.KAFKA_EVENTS_PER_SECOND}/sec ...")

    sent, failed = 0, 0
    for row in events:
        event = to_kafka_event(row)
        try:
            producer.send(config.KAFKA_TRANSACTIONS_TOPIC, key=partition_key(event), value=event)
            sent += 1
        except Exception as e:
            # Fail loudly and locally per Rules.md §4 — log and skip, don't crash the whole run.
            print(f"  WARNING: failed to send {event.get('transaction_id')}: {e}", file=sys.stderr)
            failed += 1
        if delay:
            time.sleep(delay)

    producer.flush()
    producer.close()
    print(f"Done. Sent: {sent}, Failed: {failed}")


if __name__ == "__main__":
    main()
