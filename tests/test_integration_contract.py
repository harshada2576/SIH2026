"""tests/test_integration_contract.py — Institutional Integration Contract Tests."""
from __future__ import annotations

import os
import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from audit.blockchain_lite import AuditLedger
from pipeline.integration_adapters import (
    InstitutionalIntegrationManager,
    SimulatedBankAdapter,
    SimulatedI4CAdapter,
    SimulatedLEAAdapter,
)


@pytest.fixture
def sample_case():
    return {
        "ncrpId": "CMP-2026-TEST01",
        "victimAccount": "ACC-VIC-01",
        "flaggedAccountId": "ACC-MULE-01",
        "riskScore": 0.89,
        "suspiciousExposure": 50000.0,
        "status": "BANK_HOLD_ISSUED",
        "summary": "High risk UPI fan-in cluster targeting ATM-001",
        "targetTerminal": {
            "id": "ATM-001",
            "address": "Connaught Place, New Delhi",
            "latitude": 28.63,
            "longitude": 77.22,
            "cashoutWindow": "10:00 - 10:45",
        },
        "evidence": ["Fan-in of 5 accounts", "Device fingerprint reuse"],
    }


def test_live_mode_raises_not_implemented_error(sample_case):
    """Assert INTEGRATION_MODE=live raises NotImplementedError and never falls back silently."""
    os.environ["INTEGRATION_MODE"] = "live"
    try:
        mgr = InstitutionalIntegrationManager()
        with pytest.raises(NotImplementedError) as exc_info:
            mgr.dispatch_case_decision(sample_case, "approve_forward", "BANK_OFFICIAL", "Authorized review")
        assert "Future integration" in str(exc_info.value)
    finally:
        os.environ["INTEGRATION_MODE"] = "simulated"


def test_empty_reason_raises_value_error(sample_case):
    """Assert review actions require non-empty reason string."""
    adapter = SimulatedBankAdapter()
    with pytest.raises(ValueError) as exc_info:
        adapter.send_alert(sample_case, "BANK_OFFICIAL", "  ")
    assert "reason must be non-empty" in str(exc_info.value)


def test_dismissed_case_cannot_be_dispatched_to_lea(sample_case):
    """Assert dismissed case cannot be dispatched to LEA adapter."""
    adapter = SimulatedLEAAdapter()
    dismissed_case = dict(sample_case)
    dismissed_case["status"] = "DISMISSED_FALSE_POSITIVE"

    with pytest.raises(PermissionError) as exc_info:
        adapter.send_alert(dismissed_case, "POLICE_OFFICER", "Reviewing dismissal")
    assert "Cannot dispatch case in state" in str(exc_info.value)


def test_idempotency_key_prevents_duplicate_dispatch(sample_case):
    """Assert retried dispatches return ALREADY_DISPATCHED."""
    adapter = SimulatedBankAdapter()
    ikey = "UNIQUE-IDEMPOTENCY-KEY-001"

    res1 = adapter.send_alert(sample_case, "BANK_OFFICIAL", "Initial review", idempotency_key=ikey)
    assert res1["status"] == "SENT"

    res2 = adapter.send_alert(sample_case, "BANK_OFFICIAL", "Initial review", idempotency_key=ikey)
    assert res2["status"] == "ALREADY_DISPATCHED"


def test_end_to_end_dispatch_and_ledger_verification(sample_case, tmp_path):
    """Assert full dispatch path logs to hash-chained Ed25519 audit ledger and passes ledger.verify()."""
    ledger_path = tmp_path / "audit_ledger.jsonl"
    keys_dir = tmp_path / "audit_keys"
    ledger = AuditLedger(ledger_path=ledger_path, keys_dir=keys_dir)

    mgr = InstitutionalIntegrationManager(ledger=ledger)
    res = mgr.dispatch_case_decision(sample_case, "approve_forward", "BANK_OFFICIAL", "Confirmed mule fan-in ring")

    assert res["status"] == "DISPATCH_COMPLETED"
    assert res["simulated"] is True

    # Cryptographic ledger verification
    ok, problems = ledger.verify()
    assert ok is True
    assert len(problems) == 0
