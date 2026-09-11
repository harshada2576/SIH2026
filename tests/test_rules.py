"""tests/test_rules.py — Unit tests for the 8 heuristic rules, GraphStore structural queries, and idempotence."""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from tests.helpers import acct, aid, graph_with, minutes_ago, now_utc, txn
from detection.rules import (
    account_age_rule,
    amount_movement_rule,
    device_fingerprint_rule,
    fan_in_rule,
    fan_out_rule,
    layering_rule,
    terminal_affinity_rule,
    velocity_rule,
)
from detection.scorer import evaluate_account
from pipeline.graph_store import GraphStore


# ============================================================================
# 8 HEURISTIC RULES TESTS
# ============================================================================

def test_fan_in_rule_high_when_many_senders():
    base = now_utc()
    srcs = [f"S{i:02d}" for i in range(8)]
    g = graph_with(
        [txn(f"t{i}", s, "D", 10000, minutes_ago(5, base)) for i, s in enumerate(srcs)]
    )
    r = fan_in_rule.evaluate(g, aid("D"), as_of=base)
    assert r.severity == 1.0
    assert "8 distinct account(s)" in r.measured


def test_fan_in_rule_low_for_single_sender():
    base = now_utc()
    g = graph_with([txn("t1", "A", "D", 10000, minutes_ago(5, base))])
    r = fan_in_rule.evaluate(g, aid("D"), as_of=base)
    assert r.severity == 0.0


def test_fan_out_rule_high():
    base = now_utc()
    tgts = [f"T{i:02d}" for i in range(8)]
    g = graph_with(
        [txn(f"t{i}", "A", t, 5000, minutes_ago(5, base)) for i, t in enumerate(tgts)]
    )
    r = fan_out_rule.evaluate(g, aid("A"), as_of=base)
    assert r.severity == 1.0


def test_velocity_rule_high_for_rapid_pass_through():
    base = now_utc()
    g = graph_with([
        txn("t1", "A", "B", 100000, minutes_ago(10, base)),
        txn("t2", "B", "C", 95000, minutes_ago(10, base) + timedelta(minutes=1)),
    ])
    r = velocity_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity == 1.0


def test_velocity_rule_low_for_slow_movement():
    base = now_utc()
    g = graph_with([
        txn("t1", "A", "B", 100000, minutes_ago(3 * 24 * 60, base)),
        txn("t2", "B", "C", 95000, minutes_ago(3 * 24 * 60, base) + timedelta(days=3)),
    ])
    r = velocity_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity == 0.0


def test_layering_rule_high_for_long_chain():
    base = now_utc()
    chain = ["V", "M1", "M2", "M3", "M4", "D"]
    g = graph_with([
        txn(f"t{i}", a, b, 90000 - i * 1000, minutes_ago(5 - i, base))
        for i, (a, b) in enumerate(zip(chain, chain[1:]))
    ])
    r = layering_rule.evaluate(g, aid("D"), as_of=base)
    assert r.severity == 1.0
    assert r.measured.startswith("longest incoming trail depth = 5")


def test_amount_movement_rule_high_for_onward_flow():
    base = now_utc()
    g = graph_with([
        txn("t1", "A", "B", 100000, minutes_ago(10, base)),
        txn("t2", "B", "C", 95000, minutes_ago(9, base)),
    ])
    r = amount_movement_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity == 1.0
    assert "95%" in r.measured


def test_account_age_rule_thresholds():
    base = now_utc()
    g = graph_with([], metas=[acct("NEW", age=3), acct("OLD", age=400)])
    assert account_age_rule.evaluate(g, aid("NEW"), as_of=base).severity == 1.0
    assert account_age_rule.evaluate(g, aid("OLD"), as_of=base).severity == 0.0
    unknown = graph_with([])
    assert account_age_rule.evaluate(unknown, aid("NEW"), as_of=base).severity == 0.0


def test_device_fingerprint_rule_shared_cluster():
    base = now_utc()
    g = graph_with([
        txn("t1", "A", "B", 100, minutes_ago(5, base), device="DEV-X"),
        txn("t2", "C", "B", 100, minutes_ago(4, base), device="DEV-X"),
        txn("t3", "D", "B", 100, minutes_ago(3, base), device="DEV-X"),
        txn("t4", "E", "B", 100, minutes_ago(2, base), device="DEV-X"),
        txn("t5", "F", "B", 100, minutes_ago(1, base), device="DEV-X"),
    ])
    r = device_fingerprint_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity == 1.0
    assert "5" in r.measured


def test_terminal_affinity_rule_sees_history():
    base = now_utc()
    g = graph_with(
        [txn("t1", "A", "B", 100, minutes_ago(5, base))],
        metas=[
            acct("A", terminals=["ATM-001", "ATM-002", "ATM-003"]),
            acct("B", terminals=["ATM-001"]),
        ],
    )
    r = terminal_affinity_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity > 0.0
    assert "ATM-001" in r.measured


def test_scorer_combines_signals_into_high_risk():
    """A textbook aggregator profile should cross the HIGH band (>=60/100)."""
    base = now_utc()
    srcs = [f"S{i:02d}" for i in range(8)]
    events = [txn(f"in{i}", s, "AGG", 20000, minutes_ago(5, base)) for i, s in enumerate(srcs)]
    events.append(txn("out1", "AGG", "CASH", 195000, minutes_ago(4, base)))
    g = graph_with(events, metas=[acct("AGG", age=4, terminals=["ATM-001", "ATM-002"])])
    ev = evaluate_account(g, aid("AGG"), as_of=base)
    assert ev.score >= 60.0, ev
    assert ev.band in {"HIGH", "CRITICAL"}
    assert len(ev.evidence) >= 4


def test_scorer_stays_low_for_boring_account():
    base = now_utc()
    g = graph_with(
        [txn("t1", "EMPLOYER", "ME", 50000, minutes_ago(6 * 24 * 60, base))],
        metas=[acct("ME", tier="victim", age=1500)],
    )
    ev = evaluate_account(g, aid("ME"), as_of=base)
    assert ev.score < 30.0, ev
    assert ev.band == "LOW"


# ============================================================================
# GRAPHSTORE STRUCTURAL & STREAMING QUERY TESTS
# ============================================================================

def test_recipient_does_not_share_sender_device():
    store = GraphStore(fan_window_seconds=300)
    store.add_transaction({
        "transaction_id": "TX1",
        "source_account_id": "ACC-A",
        "target_account_id": "ACC-B",
        "amount_inr": 1000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })
    store.add_transaction({
        "transaction_id": "TX2",
        "source_account_id": "ACC-A",
        "target_account_id": "ACC-C",
        "amount_inr": 2000.0,
        "timestamp": "2026-08-29T10:01:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })
    assert store.shares_device_fingerprint("ACC-B") == []
    assert store.shares_device_fingerprint("ACC-C") == []
    assert store.shares_device_fingerprint("ACC-A") == []


def test_multiple_senders_using_same_device_are_shared():
    store = GraphStore(fan_window_seconds=300)
    store.add_transaction({
        "transaction_id": "TX1",
        "source_account_id": "ACC-A",
        "target_account_id": "ACC-X",
        "amount_inr": 5000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })
    store.add_transaction({
        "transaction_id": "TX2",
        "source_account_id": "ACC-B",
        "target_account_id": "ACC-Y",
        "amount_inr": 6000.0,
        "timestamp": "2026-08-29T10:01:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })
    assert store.shares_device_fingerprint("ACC-A") == ["ACC-B"]
    assert store.shares_device_fingerprint("ACC-B") == ["ACC-A"]
    assert store.shares_device_fingerprint("ACC-X") == []
    assert store.shares_device_fingerprint("ACC-Y") == []


def test_chain_depth_progression():
    store = GraphStore(fan_window_seconds=300)
    store.add_transaction({
        "transaction_id": "TX1",
        "source_account_id": "ACC-A",
        "target_account_id": "ACC-B",
        "amount_inr": 10000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })
    store.add_transaction({
        "transaction_id": "TX2",
        "source_account_id": "ACC-B",
        "target_account_id": "ACC-C",
        "amount_inr": 9000.0,
        "timestamp": "2026-08-29T10:01:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-B",
    })
    store.add_transaction({
        "transaction_id": "TX3",
        "source_account_id": "ACC-C",
        "target_account_id": "ACC-D",
        "amount_inr": 8000.0,
        "timestamp": "2026-08-29T10:02:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-C",
    })
    assert store.account_chain_depth("ACC-A") == 0
    assert store.account_chain_depth("ACC-B") == 1
    assert store.account_chain_depth("ACC-C") == 2
    assert store.account_chain_depth("ACC-D") == 3


def test_sliding_window_pruning():
    store = GraphStore(fan_window_seconds=300)
    store.add_transaction({
        "transaction_id": "TX1",
        "source_account_id": "ACC-A",
        "target_account_id": "ACC-M",
        "amount_inr": 1000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })
    assert store.fan_in_count("ACC-M") == 1

    # TX2 is 6 minutes later -> TX1 expires
    store.add_transaction({
        "transaction_id": "TX2",
        "source_account_id": "ACC-B",
        "target_account_id": "ACC-M",
        "amount_inr": 2000.0,
        "timestamp": "2026-08-29T10:06:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-B",
    })
    assert store.fan_in_count("ACC-M") == 1
    assert store.distinct_counterparties_in_window("ACC-M") == {"ACC-B"}


def test_transaction_idempotence_and_state_preservation():
    store = GraphStore(fan_window_seconds=300)
    tx1 = {
        "transaction_id": "TX_IDEMP_001",
        "source_account_id": "ACC-SENDER",
        "target_account_id": "ACC-RECEIVER",
        "amount_inr": 5000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-SHARED",
    }
    assert store.add_transaction(tx1) is True
    assert store.fan_out_count("ACC-SENDER") == 1
    assert store.fan_in_count("ACC-RECEIVER") == 1

    # Duplicate delivery
    assert store.add_transaction(tx1) is False
    assert store.fan_out_count("ACC-SENDER") == 1
    assert store.fan_in_count("ACC-RECEIVER") == 1


def test_consumer_malformed_payload_and_poison_pill_handling():
    from pipeline.consumer import _deserialize_transaction, process_transaction

    store = GraphStore(fan_window_seconds=300)
    corrupted_bytes = b"\x00\xff\xfe INVALID_NON_JSON_BYTES"
    assert _deserialize_transaction(corrupted_bytes) is None

    valid_raw = b'{"transaction_id": "TX_VALID_1", "source_account_id": "ACC-A", "target_account_id": "ACC-B", "amount_inr": 100.0, "timestamp": "2026-08-29T10:00:00Z", "payment_channel": "UPI", "device_fingerprint": "D1"}'
    tx_dict = _deserialize_transaction(valid_raw)
    assert isinstance(tx_dict, dict)
    assert tx_dict["transaction_id"] == "TX_VALID_1"

    malformed_dict = {"transaction_id": "TX_BAD", "source_account_id": "ACC-A"}
    assert process_transaction(store, malformed_dict) == []

    signals = process_transaction(store, tx_dict)
    assert len(signals) == 2
    assert process_transaction(store, tx_dict) == []

