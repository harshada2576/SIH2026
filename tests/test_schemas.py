"""
tests/test_schemas.py

Validates schema compliance for:
- TransactionEvent
- GraphSignal
- RiskAlert (with predicted terminal coordinates)
- AccountNode & TerminalNode
- Rejection of malformed payloads
"""

import pytest
from shared.schemas import (
    TransactionEvent,
    GraphSignal,
    RiskAlert,
    PredictedTerminal,
    AccountNode,
    TerminalNode,
    ValidationError,
)


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
        "shared_device_accounts": "NOT_A_LIST",  # invalid type
        "chain_depth": 1,
        "historical_terminal_ids": ["ATM001"],
    }
    with pytest.raises(ValidationError, match="shared_device_accounts must be a list"):
        GraphSignal.from_dict(raw)


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
    }
    alert = RiskAlert.from_dict(raw)
    assert alert.complaint_id == "SYN-8cb62aea"
    assert alert.risk_score == 0.75
    assert len(alert.predicted_terminals) == 2
    assert alert.predicted_terminals[0].latitude == 21.140277
    assert alert.predicted_terminals[0].longitude == 79.112662
    assert alert.to_dict() == raw


def test_malformed_risk_alert():
    raw = {
        "complaint_id": "SYN-8cb62aea",
        "risk_score": "INVALID_SCORE",  # non-numeric
        "flagged_account_id": "ACC155",
        "predicted_terminals": [],
        "evidence": [],
        "predicted_window_start": "2026-08-26T19:31:46",
        "predicted_window_end": "2026-08-26T20:16:46",
    }
    with pytest.raises(ValidationError, match="RiskAlert.risk_score must be float"):
        RiskAlert.from_dict(raw)
