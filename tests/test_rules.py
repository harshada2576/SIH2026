"""
tests/test_rules.py

Focused unit tests for GraphStore structural queries and rules:
- Device fingerprint sharing semantics (sender-based vs recipient-based)
- Chain depth progression
- Sliding window pruning
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from pipeline.graph_store import GraphStore


def test_recipient_does_not_share_sender_device():
    """
    Test 1:
    A -> B using DEV-A
    A -> C using DEV-A
    does NOT make B and C shared-device accounts, nor does it make B or C share with A.
    """
    store = GraphStore(fan_window_seconds=300)

    store.add_transaction({
        "transaction_id": "TX1",
        "source_account_id": "A",
        "target_account_id": "B",
        "amount_inr": 1000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })

    store.add_transaction({
        "transaction_id": "TX2",
        "source_account_id": "A",
        "target_account_id": "C",
        "amount_inr": 2000.0,
        "timestamp": "2026-08-29T10:01:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })

    # B and C are mere recipients of A's payments; they did not send from DEV-A
    assert store.shares_device_fingerprint("B") == []
    assert store.shares_device_fingerprint("C") == []

    # A is the only sender using DEV-A, so A does not share with anyone yet
    assert store.shares_device_fingerprint("A") == []


def test_multiple_senders_using_same_device_are_shared():
    """
    Test 2:
    A -> X using DEV-A
    B -> Y using DEV-A
    DOES identify A and B as sharing a device (both sent from DEV-A).
    X and Y (mere recipients) do NOT share a device.
    """
    store = GraphStore(fan_window_seconds=300)

    store.add_transaction({
        "transaction_id": "TX1",
        "source_account_id": "A",
        "target_account_id": "X",
        "amount_inr": 5000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })

    store.add_transaction({
        "transaction_id": "TX2",
        "source_account_id": "B",
        "target_account_id": "Y",
        "amount_inr": 6000.0,
        "timestamp": "2026-08-29T10:01:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })

    # Senders A and B both sent transactions using DEV-A
    assert store.shares_device_fingerprint("A") == ["B"]
    assert store.shares_device_fingerprint("B") == ["A"]

    # Recipients X and Y did not send from DEV-A
    assert store.shares_device_fingerprint("X") == []
    assert store.shares_device_fingerprint("Y") == []


def test_chain_depth_progression():
    """
    Test 3:
    Linear chain: A -> B -> C -> D within window
    Depth should progress: A=0, B=1, C=2, D=3
    """
    store = GraphStore(fan_window_seconds=300)

    store.add_transaction({
        "transaction_id": "TX1",
        "source_account_id": "A",
        "target_account_id": "B",
        "amount_inr": 10000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })
    store.add_transaction({
        "transaction_id": "TX2",
        "source_account_id": "B",
        "target_account_id": "C",
        "amount_inr": 9000.0,
        "timestamp": "2026-08-29T10:01:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-B",
    })
    store.add_transaction({
        "transaction_id": "TX3",
        "source_account_id": "C",
        "target_account_id": "D",
        "amount_inr": 8000.0,
        "timestamp": "2026-08-29T10:02:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-C",
    })

    assert store.account_chain_depth("A") == 0
    assert store.account_chain_depth("B") == 1
    assert store.account_chain_depth("C") == 2
    assert store.account_chain_depth("D") == 3


def test_sliding_window_pruning():
    """
    Test 4:
    Events older than fan_window (300s) are pruned, even if out-of-order events arrive.
    """
    store = GraphStore(fan_window_seconds=300)

    # Event 1 at 10:00:00
    store.add_transaction({
        "transaction_id": "TX1",
        "source_account_id": "A",
        "target_account_id": "M",
        "amount_inr": 1000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-A",
    })
    assert store.fan_in_count("M") == 1

    # Event 2 at 10:06:00 (6 minutes later - exceeds 300s window)
    store.add_transaction({
        "transaction_id": "TX2",
        "source_account_id": "B",
        "target_account_id": "M",
        "amount_inr": 2000.0,
        "timestamp": "2026-08-29T10:06:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-B",
    })
    # TX1 should have expired from active window; only TX2 remains
    assert store.fan_in_count("M") == 1
    assert store.distinct_counterparties_in_window("M") == {"B"}


def test_scorer_modular_rules_and_dominant_aggregation():
    """
    Test 5:
    Validates independent scoring of each rule and dominant aggregation.
    """
    from detection.scorer import (
        evaluate_fan_in_rule,
        evaluate_fan_out_rule,
        evaluate_layering_rule,
        evaluate_device_rule,
        score_signal,
        build_evidence,
    )

    # 1. Pure Fan-in signal (fan_in=5)
    sig_fan_in = {
        "account_id": "ACC_MULE",
        "timestamp": "2026-08-29T10:00:00Z",
        "fan_in_count": 5,
        "fan_out_count": 0,
        "distinct_counterparties": 5,
        "shared_device_accounts": [],
        "chain_depth": 1,
        "historical_terminal_ids": ["ATM001"],
    }
    s_fi, ev_fi = evaluate_fan_in_rule(sig_fan_in)
    assert s_fi == 1.0
    assert "Rapid fan-in" in ev_fi
    assert score_signal(sig_fan_in) == 1.0

    # 2. Pure Fan-out signal (fan_out=4)
    sig_fan_out = {
        "account_id": "ACC_MULE",
        "timestamp": "2026-08-29T10:00:00Z",
        "fan_in_count": 0,
        "fan_out_count": 4,
        "distinct_counterparties": 4,
        "shared_device_accounts": [],
        "chain_depth": 0,
        "historical_terminal_ids": [],
    }
    s_fo, ev_fo = evaluate_fan_out_rule(sig_fan_out)
    assert s_fo >= 0.75
    assert "Rapid fan-out" in ev_fo
    assert score_signal(sig_fan_out) >= 0.75

    # 3. Layering aggregator (depth=3)
    sig_layering = {
        "account_id": "ACC_AGG",
        "timestamp": "2026-08-29T10:00:00Z",
        "fan_in_count": 1,
        "fan_out_count": 0,
        "distinct_counterparties": 1,
        "shared_device_accounts": [],
        "chain_depth": 3,
        "historical_terminal_ids": ["ATM002"],
    }
    s_lay, ev_lay = evaluate_layering_rule(sig_layering)
    assert s_lay == 0.95
    assert "Multi-hop layering" in ev_lay
    assert score_signal(sig_layering) == 0.95

    # 4. Device sharing
    sig_device = {
        "account_id": "ACC_FRAUD",
        "timestamp": "2026-08-29T10:00:00Z",
        "fan_in_count": 0,
        "fan_out_count": 1,
        "distinct_counterparties": 1,
        "shared_device_accounts": ["ACC_PEER"],
        "chain_depth": 0,
        "historical_terminal_ids": [],
    }
    s_dev, ev_dev = evaluate_device_rule(sig_device)
    assert s_dev == 0.90
    assert "Device reuse" in ev_dev
    assert score_signal(sig_device) == 0.90

    # 5. Normal background activity (no rules triggered)
    sig_normal = {
        "account_id": "ACC_NORMAL",
        "timestamp": "2026-08-29T10:00:00Z",
        "fan_in_count": 1,
        "fan_out_count": 0,
        "distinct_counterparties": 1,
        "shared_device_accounts": [],
        "chain_depth": 1,
        "historical_terminal_ids": [],
    }
    assert score_signal(sig_normal) < 0.25


def test_predict_terminals_includes_coordinates():
    """
    Test 6:
    Validates that predict_terminals() resolves physical latitude and longitude
    for predicted terminals from the reference data.
    """
    from detection.scorer import predict_terminals

    signal = {
        "account_id": "ACC122",
        "timestamp": "2026-08-29T10:00:00Z",
        "historical_terminal_ids": ["ATM001", "ATM002", "ATM003"],
    }

    preds = predict_terminals(signal)
    assert len(preds) == 3

    # Check first terminal (ATM001 -> Nagpur: ~21.15, ~79.08)
    assert preds[0]["terminal_id"] == "ATM001"
    assert preds[0]["probability"] == 0.90
    assert isinstance(preds[0]["latitude"], float)
    assert isinstance(preds[0]["longitude"], float)
    assert abs(preds[0]["latitude"] - 21.15) < 0.1
    assert abs(preds[0]["longitude"] - 79.08) < 0.1

    # Check probability decay across rank
    assert preds[1]["probability"] == 0.63
    assert isinstance(preds[1]["latitude"], float)
    assert preds[2]["probability"] == 0.44
    assert isinstance(preds[2]["latitude"], float)


def test_transaction_idempotence_and_state_preservation():
    """
    Test 7:
    Validates that:
    1. First delivery of a transaction is accepted.
    2. Identical duplicate delivery is rejected (returns False).
    3. Duplicate delivery does not alter fan-in, fan-out, device sharing, or chain depth.
    4. Normal different transactions continue to be accepted.
    """
    store = GraphStore(fan_window_seconds=300)

    tx1 = {
        "transaction_id": "TX_IDEMP_001",
        "source_account_id": "ACC_SENDER",
        "target_account_id": "ACC_RECEIVER",
        "amount_inr": 5000.0,
        "timestamp": "2026-08-29T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV_SHARED",
    }

    # 1. First delivery accepted
    accepted_1 = store.add_transaction(tx1)
    assert accepted_1 is True
    assert store.fan_out_count("ACC_SENDER") == 1
    assert store.fan_in_count("ACC_RECEIVER") == 1
    assert store.account_chain_depth("ACC_RECEIVER") == 1
    assert len(store.graph.edges) == 1

    # 2. Identical second delivery rejected
    accepted_2 = store.add_transaction(tx1)
    assert accepted_2 is False

    # 3. State remains exactly unchanged (no double counting)
    assert store.fan_out_count("ACC_SENDER") == 1
    assert store.fan_in_count("ACC_RECEIVER") == 1
    assert store.account_chain_depth("ACC_RECEIVER") == 1
    assert len(store.graph.edges) == 1

    # 4. Normal different transaction is accepted
    tx2 = {
        "transaction_id": "TX_IDEMP_002",
        "source_account_id": "ACC_SENDER_2",
        "target_account_id": "ACC_RECEIVER",
        "amount_inr": 3000.0,
        "timestamp": "2026-08-29T10:01:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV_SHARED",
    }
    accepted_3 = store.add_transaction(tx2)
    assert accepted_3 is True
    assert store.fan_in_count("ACC_RECEIVER") == 2
    assert store.shares_device_fingerprint("ACC_SENDER") == ["ACC_SENDER_2"]
    assert len(store.graph.edges) == 2




