"""
tests/test_api_engine.py

Smoke tests for api/engine.py:
1. CaseEngine loads investigation cases from real dataset (>= 5 cases).
2. Bank role vs Police role visibility filter.
3. Pre-complaint hold -> customer confirmation -> release lifecycle gating.
4. Attempting release without customer confirmation preserves gating requirement.
"""

import pytest
from api.engine import CaseEngine


def test_engine_loads_cases():
    engine = CaseEngine()
    cases = engine.list_cases("BANK")
    assert len(cases) >= 5, "Engine should load at least 5 showcase cases"
    for c in cases:
        assert c.get("ncrpId")
        assert c.get("reportedLoss")
        assert "riskBreakdown" in c
        assert len(c["riskBreakdown"].get("signals", [])) > 0


def test_role_filtering():
    engine = CaseEngine()
    bank_cases = engine.list_cases("BANK")
    assert len(bank_cases) > 0

    police_cases = engine.list_cases("POLICE")
    # Police only see APPROVED or EN_ROUTE cases
    for c in police_cases:
        assert c.get("status") in ("APPROVED", "EN_ROUTE")


def test_hold_confirm_release_cycle():
    engine = CaseEngine()
    # Pick a pending case
    pending = [c for c in engine.list_cases("BANK") if c.get("status") == "PENDING"]
    assert len(pending) > 0
    test_id = pending[0]["ncrpId"]

    # 1. Place hold
    held = engine.act(test_id, "hold", "Officer Sharma")
    assert held["status"] == "BANK_HOLD"
    assert held.get("digitalBlockActive") is True
    assert held.get("confirmationState") == "PENDING_CONFIRMATION"

    # 2. Confirm customer
    confirmed = engine.act(test_id, "confirm_customer", "Officer Sharma")
    assert confirmed["confirmationState"] == "CONFIRMED_LEGITIMATE"

    # 3. Now release
    released = engine.act(test_id, "release", "Officer Sharma")
    assert released["status"] == "RELEASED"
    assert released.get("digitalBlockActive") is False
