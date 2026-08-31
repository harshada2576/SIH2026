"""tests/test_integration.py

End-to-end integration tests:
1. Kafka streaming pipeline smoke test (producer -> consumer -> graph_store -> graph_signals).
2. Direct terminal ranking and priority sorting.
3. High-risk money trail analysis, time window estimation, and alert construction.
4. Alert dispatcher formatting and console logging.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from detection.alert_dispatcher import dispatch
from detection.scorer import analyze
from detection.terminal_ranking import rank_terminals
from pipeline.consumer import process_transaction
from pipeline.graph_store import GraphStore
from shared.kafka_utils import (
    GRAPH_SIGNALS_TOPIC,
    KAFKA_BOOTSTRAP_SERVERS,
    TRANSACTIONS_TOPIC,
    get_kafka_consumer,
    get_kafka_producer,
    is_kafka_available,
)
from shared.schemas import GraphSignal, TerminalNode
from tests.helpers import acct, aid, graph_with, minutes_ago, now_utc, txn


def _terminals():
    """Two districts; T1 close & historical, T2 far & historical, T3 unrelated."""
    return [
        TerminalNode(
            terminal_id="ATM-001",
            terminal_type="ATM_KIOSK",
            latitude=28.60,
            longitude=77.20,
            district_pincode="110001",
        ),
        TerminalNode(
            terminal_id="ATM-002",
            terminal_type="ATM_KIOSK",
            latitude=28.57,
            longitude=77.32,
            district_pincode="201301",
        ),
        TerminalNode(
            terminal_id="POS-001",
            terminal_type="POS",
            latitude=28.61,
            longitude=77.19,
            district_pincode="110001",
        ),
    ]


def test_rank_terminals_puts_historical_close_terminal_first():
    base = now_utc()
    g = graph_with(
        [txn("t1", "EMPLOYER", "ME", 50000, minutes_ago(5, base))],
        metas=[acct("ME", pincode="110001", terminals=["ATM-001", "ATM-002"])],
    )
    ranked = rank_terminals(g, aid("ME"), _terminals(), window_start=base)
    assert ranked[0].terminal.terminal_id == "ATM-001"
    assert ranked[0].priority > ranked[-1].priority


def test_analyze_returns_alert_for_high_risk_trail():
    base = now_utc()
    chain = ["VICTIM", "M1", "M2", "AGG"]
    events = [
        txn(f"t{i}", a, b, 90000 - i * 5000, minutes_ago(5 - i, base))
        for i, (a, b) in enumerate(zip(chain, chain[1:]))
    ]
    events += [txn(f"in{i}", f"S{i:02d}", "AGG", 15000, minutes_ago(4, base)) for i in range(6)]
    events.append(txn("cashout", "AGG", "ACC-CASH", 240000, minutes_ago(3, base)))
    g = graph_with(
        events,
        metas=[acct("AGG", age=5, pincode="110001", terminals=["ATM-001", "ATM-002"])],
    )
    alert = analyze(g, aid("AGG"), terminals=_terminals(), as_of=base)
    assert alert is not None
    assert alert.risk_score >= 0.6
    assert alert.flagged_account_id == aid("AGG")
    assert alert.evidence
    assert alert.predicted_terminals
    probs = [t.probability for t in alert.predicted_terminals]
    assert probs == sorted(probs, reverse=True)
    assert alert.predicted_window_start < alert.predicted_window_end
    assert "Money trail:" in alert.evidence[0]


def test_analyze_returns_none_below_threshold():
    base = now_utc()
    g = graph_with(
        [txn("t1", "EMPLOYER", "ME", 50000, minutes_ago(5, base))],
        metas=[acct("ME", tier="victim", age=1500)],
    )
    assert analyze(g, aid("ME"), terminals=_terminals(), as_of=base) is None


def test_end_to_end_smoke_with_dispatch(capsys):
    """Produce events -> graph -> analyze -> dispatch (prints investigator alert)."""
    base = now_utc()
    chain = ["VICTIM", "M1", "M2", "AGG"]
    events = [
        txn(f"t{i}", a, b, 90000 - i * 5000, minutes_ago(5 - i, base))
        for i, (a, b) in enumerate(zip(chain, chain[1:]))
    ]
    events += [txn(f"in{i}", f"S{i:02d}", "AGG", 15000, minutes_ago(4, base)) for i in range(6)]
    events.append(txn("cashout", "AGG", "ACC-CASH", 240000, minutes_ago(3, base)))
    g = graph_with(
        events,
        metas=[acct("AGG", age=5, pincode="110001", terminals=["ATM-001", "ATM-002"])],
    )
    alert = analyze(g, aid("AGG"), terminals=_terminals(), as_of=base)
    assert alert is not None
    dispatch(alert)
    out = capsys.readouterr().out
    assert "ALERT" in out
    assert alert.complaint_id in out
    assert "PREDICTED CASH-OUT" in out


# ============================================================================
# KAFKA LIVE PIPELINE INTEGRATION TEST
# ============================================================================

@pytest.fixture(scope="module")
def kafka_ready():
    """Verifies that the Kafka broker is running before executing integration tests."""
    if not is_kafka_available(KAFKA_BOOTSTRAP_SERVERS, timeout_sec=2.0):
        pytest.skip(f"Kafka broker not reachable at {KAFKA_BOOTSTRAP_SERVERS}. Skipping live test.")
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

    # 2. Consume from "transactions"
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
        sig_obj = GraphSignal.from_dict(sig)
        assert sig_obj.account_id in (src_acc, tgt_acc)
        producer.send(GRAPH_SIGNALS_TOPIC, value=sig)
    producer.flush(timeout=5)

    # 4. Consume from "graph_signals"
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

    # 5. Duplicate Delivery Test
    dup_signals = process_transaction(store, found_tx)
    assert dup_signals == [], "Duplicate transaction must be rejected by GraphStore idempotence"

    producer.close()
