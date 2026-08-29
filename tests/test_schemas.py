"""Validate the 4 schemas accept good payloads and reject bad ones (Architecture.md §6)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.schemas import (
    AccountNodeMetadata, PredictedTerminal, RiskAlert, TerminalNode, TransactionEvent,
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


def test_transaction_event_parses_sample():
    ev = TransactionEvent(** _txn_dict())
    assert ev.source_account_id == "ACC-00042"
    assert ev.amount_inr == 15000.0


@pytest.mark.parametrize("bad_field,bad_value", [
    ("payment_channel", "CREDIT_CARD"),   # not in the locked enum
    ("source_account_id", "not-an-account"),
    ("amount_inr", -5),                    # money amounts must be positive
])
def test_transaction_event_rejects_invalid(bad_field, bad_value):
    d = _txn_dict()
    d[bad_field] = bad_value
    with pytest.raises(ValidationError):
        TransactionEvent(**d)


def test_account_metadata_defaults():
    a = AccountNodeMetadata(account_id="ACC-00321", account_tier="mule_l1",
                            account_age_days=12, historical_terminal_ids=["ATM-001"])
    assert a.historical_terminal_ids == ["ATM-001"]
    assert a.district_pincode is None


def test_terminal_node_range_validation():
    with pytest.raises(ValidationError):
        TerminalNode(terminal_id="ATM-X", terminal_type="ATM_KIOSK",
                     latitude=95.0, longitude=0.0, district_pincode="110001")


def test_risk_alert_roundtrip():
    a = RiskAlert(
        complaint_id="CMP-2026-000451",
        risk_score=0.91,
        flagged_account_id="ACC-00891",
        predicted_terminals=[
            PredictedTerminal(terminal_id="ATM-SBI-ND-042", probability=0.87,
                              latitude=28.57, longitude=77.32),
        ],
        evidence=["Fan-in of 5 accounts within 3 minutes"],
        predicted_window_start="2026-09-01T10:30:00Z",
        predicted_window_end="2026-09-01T11:15:00Z",
    )
    assert a.risk_score <= 1.0
    assert a.predicted_terminals[0].terminal_id == "ATM-SBI-ND-042"


def test_risk_score_bounds():
    with pytest.raises(ValidationError):
        RiskAlert(complaint_id="X", risk_score=1.5, flagged_account_id="ACC-1",
                  predicted_window_start="2026-09-01T10:30:00Z",
                  predicted_window_end="2026-09-01T11:15:00Z")