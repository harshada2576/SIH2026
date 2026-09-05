"""tests/test_schemas.py

Validates schema compliance and failure modes for:
- TransactionEvent (Architecture.md §6.1)
- AccountNodeMetadata / AccountNode (Architecture.md §6.2)
- TerminalNode (Architecture.md §6.3)
- RiskAlert & PredictedTerminal (Architecture.md §6.4)
- GraphSignal (Kafka intermediate topic contract)
- Rejection of malformed / out-of-bound payloads
"""
from __future__ import annotations

import pytest
from shared.schemas import (
    AccountNodeMetadata,
    AccountNode,
    GraphSignal,
    PredictedTerminal,
    RiskAlert,
    TerminalNode,
    TransactionEvent,
    ValidationError,
)


def _txn_dict():
    return {
        "transaction_id": "TXN-8f2a1e",
        "source_account_id": "ACC-00042",
        "target_account_id": "ACC-00891",
        "amount_inr": 15000.0,
        "timestamp": "2026-09-01T10:14:22Z",
        "payment_channel": "UPI",
        "device_fingerprint": "hash-string",
    }


def test_valid_transaction_event():
    raw = {
        "transaction_id": "TXN-88219401",
        "source_account_id": "ACC-00412",
        "target_account_id": "ACC-00891",
        "amount_inr": 48500.00,
        "timestamp": "2026-09-01T10:14:22Z",
        "payment_channel": "IMPS",
        "device_fingerprint": "FP-9a8b7c",
    }
    tx = TransactionEvent.from_dict(raw)
    assert tx.transaction_id == "TXN-88219401"
    assert tx.amount_inr == 48500.0
    assert tx.to_dict() == raw
    assert tx.timestamp_utc is not None


def test_transaction_event_parses_sample():
    ev = TransactionEvent(**_txn_dict())
    assert ev.source_account_id == "ACC-00042"
    assert ev.amount_inr == 15000.0


@pytest.mark.parametrize("bad_field,bad_value", [
    ("payment_channel", "CREDIT_CARD"),   # not in the locked enum
    ("source_account_id", "INVALID_NO_PREFIX"),
    ("amount_inr", -5),                    # money amounts must be positive
])
def test_transaction_event_rejects_invalid(bad_field, bad_value):
    d = _txn_dict()
    d[bad_field] = bad_value
    with pytest.raises(ValidationError):
        TransactionEvent(**d)


def test_malformed_transaction_event_missing_field():
    raw = {
        "transaction_id": "TXN-88219401",
        "source_account_id": "ACC-00412",
        # missing target_account_id
        "amount_inr": 48500.00,
        "timestamp": "2026-09-01T10:14:22Z",
        "payment_channel": "IMPS",
        "device_fingerprint": "FP-9a8b7c",
    }
    with pytest.raises(ValidationError, match="Missing required field in TransactionEvent"):
        TransactionEvent.from_dict(raw)


def test_valid_graph_signal():
    raw = {
        "account_id": "ACC001",
        "timestamp": "2026-08-29T10:00:00Z",
        "fan_in_count": 4,
        "fan_out_count": 0,
        "distinct_counterparties": 4,
        "shared_device_accounts": ["ACC002"],
        "chain_depth": 1,
        "historical_terminal_ids": ["ATM001", "ATM002"],
    }
    sig = GraphSignal.from_dict(raw)
    assert sig.account_id == "ACC001"
    assert sig.fan_in_count == 4
    assert sig.shared_device_accounts == ["ACC002"]
    assert sig.to_dict() == raw


def test_malformed_graph_signal_invalid_type():
    raw = {
        "account_id": "ACC001",
        "timestamp": "2026-08-29T10:00:00Z",
        "fan_in_count": 4,
        "fan_out_count": 0,
        "distinct_counterparties": 4,
        "shared_device_accounts": "NOT_A_LIST",
        "chain_depth": 1,
        "historical_terminal_ids": ["ATM001"],
    }
    with pytest.raises(ValidationError, match="shared_device_accounts must be a list"):
        GraphSignal.from_dict(raw)


def test_account_metadata_defaults():
    a = AccountNodeMetadata(
        account_id="ACC-00321",
        account_tier="mule_l1",
        account_age_days=12,
        historical_terminal_ids=["ATM-001"],
    )
    assert a.historical_terminal_ids == ["ATM-001"]
    assert a.district_pincode is None


def test_terminal_node_range_validation():
    with pytest.raises(ValidationError):
        TerminalNode(
            terminal_id="ATM-X",
            terminal_type="ATM_KIOSK",
            latitude=95.0,  # Invalid latitude (>90)
            longitude=0.0,
            district_pincode="110001",
        )


def test_valid_risk_alert_with_coordinates():
    raw = {
        "complaint_id": "SYN-8cb62aea",
        "risk_score": 0.75,
        "flagged_account_id": "ACC155",
        "predicted_terminals": [
            {
                "terminal_id": "ATM038",
                "probability": 0.9,
                "latitude": 21.140277,
                "longitude": 79.112662,
            },
            {
                "terminal_id": "ATM017",
                "probability": 0.63,
                "latitude": 21.161327,
                "longitude": 79.098063,
            },
        ],
        "evidence": [
            "Intermediate layering: Account is a pass-through node (depth 2) in a rapid multi-hop chain"
        ],
        "predicted_window_start": "2026-08-26T19:31:46.576165",
        "predicted_window_end": "2026-08-26T20:16:46.576165",
        "confidence": 0.82,
    }
    alert = RiskAlert.from_dict(raw)
    assert alert.complaint_id == "SYN-8cb62aea"
    assert alert.risk_score == 0.75
    assert alert.confidence == 0.82
    assert len(alert.predicted_terminals) == 2
    assert alert.predicted_terminals[0].latitude == 21.140277
    assert alert.predicted_terminals[0].longitude == 79.112662
    assert alert.to_dict() == raw


def test_risk_alert_roundtrip():
    a = RiskAlert(
        complaint_id="CMP-2026-000451",
        risk_score=0.91,
        flagged_account_id="ACC-00891",
        predicted_terminals=[
            PredictedTerminal(
                terminal_id="ATM-SBI-ND-042",
                probability=0.87,
                latitude=28.57,
                longitude=77.32,
            ),
        ],
        evidence=["Fan-in of 5 accounts within 3 minutes"],
        predicted_window_start="2026-09-01T10:30:00Z",
        predicted_window_end="2026-09-01T11:15:00Z",
        confidence=0.88,
    )
    assert a.risk_score <= 1.0
    assert a.confidence == 0.88
    assert a.predicted_terminals[0].terminal_id == "ATM-SBI-ND-042"


def test_risk_score_bounds():
    with pytest.raises(ValidationError):
        RiskAlert(
            complaint_id="X",
            risk_score=1.5,  # Out of range [0, 1]
            flagged_account_id="ACC-1",
            predicted_window_start="2026-09-01T10:30:00Z",
            predicted_window_end="2026-09-01T11:15:00Z",
        )
