"""
tests/test_integration.py

Automated Kafka integration smoke test:
1. Probes Kafka availability (skips gracefully if broker offline).
2. Publishes a live transaction to "transactions" topic.
3. Consumes event, updates GraphStore, and emits signal to "graph_signals" topic.
4. Consumes from "graph_signals" and verifies schema conformity (GraphSignal).
5. Validates that re-delivering the same transaction ID is safely deduplicated.
"""

import json
import sys
import time
import uuid
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from shared.kafka_utils import (
    KAFKA_BOOTSTRAP_SERVERS,
    TRANSACTIONS_TOPIC,
    GRAPH_SIGNALS_TOPIC,
    is_kafka_available,
    get_kafka_producer,
    get_kafka_consumer,
)
from shared.schemas import GraphSignal
from pipeline.graph_store import GraphStore
from pipeline.consumer import process_transaction


@pytest.fixture(scope="module")
def kafka_ready():
    """Verifies that the Kafka broker is running before executing integration tests."""
    if not is_kafka_available(KAFKA_BOOTSTRAP_SERVERS, timeout_sec=2.0):
        pytest.skip(f"Kafka broker not reachable at {KAFKA_BOOTSTRAP_SERVERS}. Skipping integration test.")
    return True


def test_kafka_pipeline_end_to_end_smoke(kafka_ready):
    """
    Smoke test: Produces a transaction to Kafka, consumes and processes it into GraphStore,
    publishes graph_signals, and verifies schema compliance.
    """
    store = GraphStore(fan_window_seconds=300)
    producer = get_kafka_producer(KAFKA_BOOTSTRAP_SERVERS)

    unique_id = f"SMOKE_{uuid.uuid4().hex[:8]}"
    src_acc = f"ACC_SMOKE_SRC_{uuid.uuid4().hex[:4]}"
    tgt_acc = f"ACC_SMOKE_TGT_{uuid.uuid4().hex[:4]}"

    test_tx = {
        "transaction_id": unique_id,
        "source_account_id": src_acc,
        "target_account_id": tgt_acc,
        "amount_inr": 25000.0,
        "timestamp": "2026-08-29T12:00:00Z",
        "payment_channel": "IMPS",
        "device_fingerprint": "DEV_SMOKE_01",
    }

    # 1. Publish transaction to Kafka topic "transactions"
    producer.send(TRANSACTIONS_TOPIC, key=src_acc, value=test_tx)
    producer.flush(timeout=5)

    # 2. Consume from "transactions" with a unique temporary group ID
    consumer_tx = get_kafka_consumer(
        TRANSACTIONS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"test-smoke-tx-group-{uuid.uuid4().hex[:6]}",
        auto_offset_reset="earliest",
        consumer_timeout_ms=5000,
    )

    found_tx = None
    for msg in consumer_tx:
        if msg.value and msg.value.get("transaction_id") == unique_id:
            found_tx = msg.value
            break
    consumer_tx.close()

    assert found_tx is not None, f"Transaction {unique_id} was not received from Kafka topic '{TRANSACTIONS_TOPIC}'"

    # 3. Process transaction in GraphStore and publish signals to "graph_signals"
    signals = process_transaction(store, found_tx)
    assert len(signals) == 2

    for sig in signals:
        # Validate schema dataclass
        sig_obj = GraphSignal.from_dict(sig)
        assert sig_obj.account_id in (src_acc, tgt_acc)
        producer.send(GRAPH_SIGNALS_TOPIC, value=sig)
    producer.flush(timeout=5)

    # 4. Consume from "graph_signals" to verify round-trip message delivery
    consumer_sig = get_kafka_consumer(
        GRAPH_SIGNALS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"test-smoke-sig-group-{uuid.uuid4().hex[:6]}",
        auto_offset_reset="earliest",
        consumer_timeout_ms=5000,
    )

    received_account_ids = set()
    start_time = time.time()
    for msg in consumer_sig:
        if msg.value and msg.value.get("account_id") in (src_acc, tgt_acc):
            sig_obj = GraphSignal.from_dict(msg.value)
            received_account_ids.add(sig_obj.account_id)
            if len(received_account_ids) == 2:
                break
        if time.time() - start_time > 5.0:
            break
    consumer_sig.close()

    assert src_acc in received_account_ids
    assert tgt_acc in received_account_ids

    # 5. Duplicate Delivery Test: Process identical transaction again
    dup_signals = process_transaction(store, found_tx)
    assert dup_signals == [], "Duplicate transaction must be rejected by GraphStore idempotence"

    producer.close()
