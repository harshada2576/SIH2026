"""tests/test_phase2_audit_and_intervention.py — audit ledger tamper detection
and auto-intervention tiering decisions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from audit.blockchain_lite import AuditLedger
from detection import auto_intervention
from shared.schemas import RiskAlert


@pytest.fixture()
def tmp_ledger(tmp_path):
    return AuditLedger(ledger_path=tmp_path / "ledger.jsonl", keys_dir=tmp_path / "keys")


def test_ledger_verifies_clean_chain(tmp_ledger):
    for i in range(3):
        tmp_ledger.append({"complaint_id": f"CMP-{i}", "risk_score": 0.5 + i * 0.1})
    ok, problems = tmp_ledger.verify()
    assert ok
    assert problems == []


def test_ledger_detects_payload_tampering(tmp_ledger):
    tmp_ledger.append({"complaint_id": "CMP-0", "risk_score": 0.4})
    tmp_ledger.append({"complaint_id": "CMP-1", "risk_score": 0.9})

    lines = tmp_ledger.ledger_path.read_text().splitlines()
    block = json.loads(lines[1])
    block["payload"]["risk_score"] = 0.1  # tamper without touching hash/signature
    lines[1] = json.dumps(block)
    tmp_ledger.ledger_path.write_text("\n".join(lines) + "\n")

    ok, problems = tmp_ledger.verify()
    assert not ok
    assert any("TAMPERED" in p for p in problems)


def test_ledger_detects_broken_chain(tmp_ledger):
    tmp_ledger.append({"complaint_id": "CMP-0"})
    tmp_ledger.append({"complaint_id": "CMP-1"})
    tmp_ledger.append({"complaint_id": "CMP-2"})

    lines = tmp_ledger.ledger_path.read_text().splitlines()
    del lines[1]  # remove the middle block entirely
    tmp_ledger.ledger_path.write_text("\n".join(lines) + "\n")

    ok, problems = tmp_ledger.verify()
    assert not ok
    assert any("CHAIN BROKEN" in p for p in problems)


def _alert(risk_score: float, confidence: float) -> RiskAlert:
    return RiskAlert(
        complaint_id="CMP-TEST", risk_score=risk_score, flagged_account_id="ACC-TEST",
        predicted_terminals=[], evidence=["e1", "e2"],
        predicted_window_start="2026-09-04T00:00:00Z", predicted_window_end="2026-09-04T01:00:00Z",
        confidence=confidence,
    )


def test_critical_high_confidence_triggers_auto_freeze():
    decision = auto_intervention.decide(_alert(0.85, 0.9), band="CRITICAL")
    assert decision.tier == "AUTO_FREEZE"
    assert decision.bank_action == "freeze"
    assert decision.lea_notified


def test_critical_low_confidence_triggers_hold_not_freeze():
    decision = auto_intervention.decide(_alert(0.85, 0.3), band="CRITICAL")
    assert decision.tier == "AUTO_HOLD"
    assert decision.bank_action == "hold"


def test_high_band_triggers_soft_notify_only():
    decision = auto_intervention.decide(_alert(0.65, 0.9), band="HIGH")
    assert decision.tier == "SOFT_NOTIFY"
    assert decision.bank_action == "notify"


def test_medium_band_takes_no_action():
    decision = auto_intervention.decide(_alert(0.4, 0.9), band="MEDIUM")
    assert decision.tier == "LOG_ONLY"
    assert decision.bank_action is None
    assert not decision.lea_notified
