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

import json
import logging
from kafka import KafkaConsumer, KafkaProducer

from graph_store import GraphStore

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("consumer")

KAFKA_BOOTSTRAP = "localhost:9092"
TRANSACTIONS_TOPIC = "transactions"
SIGNALS_TOPIC = "graph_signals"

FAN_ALERT_THRESHOLD = 3  # emit a signal-worth-watching once an account sees >= this many
                          # in-window in/out edges; tune once real synthetic data is in


def build_signal(store: GraphStore, account_id: str, ts) -> dict:
    return {
        "account_id": account_id,
        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        "fan_in_count": store.fan_in_count(account_id),
        "fan_out_count": store.fan_out_count(account_id),
        "distinct_counterparties": len(store.distinct_counterparties_in_window(account_id)),
        "shared_device_accounts": store.shares_device_fingerprint(account_id),
        "account_tier": store.accounts.get(account_id, {}).get("account_tier", "unknown"),
        "chain_depth": store.account_chain_depth(account_id),
        "historical_terminal_ids": store.historical_terminal_affinity(account_id),
    }


def load_reference_data(store: GraphStore, accounts_path: str, terminals_path: str):
    """
    Loads the static Accounts and Terminals datasets (produced by accounts.py /
    terminals.py) once at startup. Adjust format (CSV/JSON) to whatever those
    scripts actually output.
    """
    with open(accounts_path) as f:
        accounts = json.load(f)
    with open(terminals_path) as f:
        terminals = json.load(f)
    store.load_accounts(accounts)
    store.load_terminals(terminals)
    log.info(f"Loaded {len(accounts)} accounts and {len(terminals)} terminals")


def run(accounts_path: str = "../data/accounts.json",
        terminals_path: str = "../data/terminals.json"):

    store = GraphStore(fan_window_seconds=300)
    load_reference_data(store, accounts_path, terminals_path)

    consumer = KafkaConsumer(
        TRANSACTIONS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        group_id="graph-builder-group",
    )

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    log.info("Consumer started, listening for transactions...")

    for message in consumer:
        tx = message.value
        try:
            store.add_transaction(tx)
        except KeyError as e:
            log.error(f"Malformed transaction, missing field {e}: {tx}")
            continue

        # Emit a signal for both parties in the transaction — cheap to compute,
        # lets the scorer decide what crosses its own risk threshold.
        for account_id in (tx["source_account_id"], tx["target_account_id"]):
            signal = build_signal(store, account_id, tx["timestamp"])
            producer.send(SIGNALS_TOPIC, value=signal)

            if signal["fan_in_count"] >= FAN_ALERT_THRESHOLD or signal["fan_out_count"] >= FAN_ALERT_THRESHOLD:
                log.info(f"Elevated activity: {account_id} -> {signal}")

    producer.flush()


if __name__ == "__main__":
    run()
