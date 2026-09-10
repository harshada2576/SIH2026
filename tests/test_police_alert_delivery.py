"""tests/test_police_alert_delivery.py — Unit tests for Part 5: Police Alert App & Delivery.

Tests mandatory requirements A through I:
- Test A: Create police alert
- Test B: Verify alert contents (incident, origin tx, money trail, accounts, withdrawals, locations, timeline, evidence)
- Test C: Police alert delivery/queue retrieval
- Test D: Acknowledge alert (SENT -> ACKNOWLEDGED, timestamp, status sync)
- Test E: Investigation status update (UNDER_INVESTIGATION -> RESOLVED)
- Test F: Idempotency & duplicate submission prevention
- Test G: Invalid case rejection
- Test H: Authorization enforcement (role checks)
- Test I: SQLite persistence across restarts
"""
import tempfile
from pathlib import Path
import pytest

from pipeline.police_alert_delivery import PoliceAlertManager
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from shared.persistence import Store
from shared.schemas import CaseRecord, PoliceAlertStatus, PredictedTerminal, TransactionEvent


@pytest.fixture
def test_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cybershield.db"
        store = Store(db_path=db_path)
        yield store
        store.close()


@pytest.fixture
def setup_test_case(test_db):
    """Seed a sample investigation case with money trail and withdrawal attempt."""
    case_id = "CASE-TEST-POLICE-001"
    flagged_account = "ACC-MULE-888"

    # Seed transaction
    tx = TransactionEvent(
        transaction_id="TXN-ROOT-001",
        source_account_id="ACC-VICTIM-101",
        target_account_id=flagged_account,
        amount_inr=150000.0,
        timestamp="2026-09-10T10:00:00Z",
        payment_channel="IMPS",
        device_fingerprint="DEV-FINGERPRINT-999",
    )
    test_db.save_transaction(tx)

    # Seed case
    case = CaseRecord(
        case_id=case_id,
        flagged_account_id=flagged_account,
        state="PRE_COMPLAINT_INTERVENTION",
        risk_score=0.92,
        confidence=0.88,
        band="CRITICAL",
        suspicious_amount=150000.0,
        protected_amount=150000.0,
        existing_balance=25000.0,
        money_trail=[
            {
                "hop_index": 1,
                "source_account_id": "ACC-VICTIM-101",
                "target_account_id": flagged_account,
                "amount_inr": 150000.0,
                "timestamp": "2026-09-10T10:00:00Z",
                "payment_channel": "IMPS",
                "suspicious_flags": ["SUSPICIOUS_HIGH_VALUE"],
            },
            {
                "hop_index": 2,
                "source_account_id": flagged_account,
                "target_account_id": "ACC-AGGREGATOR-999",
                "amount_inr": 140000.0,
                "timestamp": "2026-09-10T10:05:00Z",
                "payment_channel": "UPI",
                "suspicious_flags": ["RAPID_FORWARDING"],
            },
        ],
        predicted_terminals=[
            PredictedTerminal(
                terminal_id="ATM-SBI-ND-042",
                probability=0.89,
                latitude=28.5708,
                longitude=77.3261,
            )
        ],
        evidence=[
            "Rapid forwarding through multiple accounts",
            "Multiple suspicious inbound transfers",
            "Predicted cashout terminal targeted",
        ],
    )
    test_db.save_case(case)

    # Seed withdrawal attempt
    geo = WithdrawalGeoIntelligence(store=test_db)
    geo.process_withdrawal_attempt(
        attempt_id="ATT-TEST-001",
        account_id="ACC-AGGREGATOR-999",
        terminal_id="ATM-SBI-ND-042",
        amount_inr=10000.0,
        timestamp="2026-09-10T10:14:00Z",
        case_id=case_id,
    )

    return case_id, test_db


# ----------------------------------------------------------------------------
# Test A — Create Police Alert
# ----------------------------------------------------------------------------
def test_a_create_police_alert(setup_test_case):
    case_id, store = setup_test_case
    mgr = PoliceAlertManager(store=store)

    alert = mgr.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL", source="CyberShield")

    assert alert is not None
    assert alert.police_alert_id.startswith("POL-ALERT-")
    assert alert.case_id == case_id
    assert alert.alert_status == PoliceAlertStatus.SENT
    assert alert.priority == "CRITICAL"

    # Verify persisted in SQLite
    persisted = store.get_police_alert(alert.police_alert_id)
    assert persisted is not None
    assert persisted["case_id"] == case_id


# ----------------------------------------------------------------------------
# Test B — Alert Contents Validation
# ----------------------------------------------------------------------------
def test_b_alert_contents(setup_test_case):
    case_id, store = setup_test_case
    mgr = PoliceAlertManager(store=store)

    alert = mgr.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL")

    # 1. Incident
    assert alert.incident["case_id"] == case_id
    assert alert.incident["risk_score"] == 0.92
    assert alert.incident["risk_level"] == "CRITICAL"
    assert "reason_for_escalation" in alert.incident

    # 2. Origin transaction
    assert alert.origin_transaction["origin_account"] in ("ACC-VICTIM-101", "ACC-MULE-888")
    assert alert.origin_transaction["amount"] > 0

    # 3. Money trail
    assert len(alert.money_trail) >= 1
    assert alert.money_trail[0]["source_account"] == "ACC-VICTIM-101"

    # 4. Relevant accounts
    assert "ACC-MULE-888" in alert.relevant_accounts or "ACC-VICTIM-101" in alert.relevant_accounts

    # 5. Withdrawal attempts
    assert len(alert.withdrawal_attempts) >= 1
    att = alert.withdrawal_attempts[0]
    assert att["terminal_id"] == "ATM-SBI-ND-042"
    assert att["amount"] == 10000.0

    # 6. Timeline & Evidence
    assert len(alert.location_timeline) >= 1
    assert len(alert.evidence) >= 1


# ----------------------------------------------------------------------------
# Test C — Delivery / Queue Retrieval
# ----------------------------------------------------------------------------
def test_c_delivery_queue(setup_test_case):
    case_id, store = setup_test_case
    mgr = PoliceAlertManager(store=store)

    mgr.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL")

    alerts = mgr.list_police_alerts(limit=10)
    assert len(alerts) >= 1
    assert alerts[0]["case_id"] == case_id


# ----------------------------------------------------------------------------
# Test D — Acknowledge Alert
# ----------------------------------------------------------------------------
def test_d_acknowledge_alert(setup_test_case):
    case_id, store = setup_test_case
    mgr = PoliceAlertManager(store=store)

    created = mgr.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL")
    assert created.alert_status == PoliceAlertStatus.SENT

    ack = mgr.acknowledge_police_alert(
        police_alert_id=created.police_alert_id,
        caller_role="POLICE_OFFICER",
        officer_id="INSPECTOR-VERMA",
    )

    assert ack.alert_status == PoliceAlertStatus.ACKNOWLEDGED
    assert ack.acknowledged_by == "INSPECTOR-VERMA"
    assert ack.acknowledged_at is not None

    # Verify CyberShield case status synchronized
    synced_case = store.get_case(case_id)
    assert synced_case["lea_notification_status"] == PoliceAlertStatus.ACKNOWLEDGED


# ----------------------------------------------------------------------------
# Test E — Investigation Status Update
# ----------------------------------------------------------------------------
def test_e_investigation_status(setup_test_case):
    case_id, store = setup_test_case
    mgr = PoliceAlertManager(store=store)

    created = mgr.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL")
    mgr.acknowledge_police_alert(police_alert_id=created.police_alert_id, caller_role="POLICE_OFFICER")

    # Move to UNDER_INVESTIGATION
    inv = mgr.update_investigation_status(
        police_alert_id=created.police_alert_id,
        new_status=PoliceAlertStatus.UNDER_INVESTIGATION,
        caller_role="POLICE_OFFICER",
        notes="Field team dispatched to Sector 20 ATM",
    )
    assert inv.alert_status == PoliceAlertStatus.UNDER_INVESTIGATION

    # Move to RESOLVED
    res = mgr.update_investigation_status(
        police_alert_id=created.police_alert_id,
        new_status=PoliceAlertStatus.RESOLVED,
        caller_role="POLICE_OFFICER",
    )
    assert res.alert_status == PoliceAlertStatus.RESOLVED

    # Verify CyberShield state synchronized
    synced_case = store.get_case(case_id)
    assert synced_case["lea_notification_status"] == PoliceAlertStatus.RESOLVED


# ----------------------------------------------------------------------------
# Test F — Duplicate Submission (Idempotency)
# ----------------------------------------------------------------------------
def test_f_duplicate_submission(setup_test_case):
    case_id, store = setup_test_case
    mgr = PoliceAlertManager(store=store)

    first = mgr.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL")
    second = mgr.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL")

    assert first.police_alert_id == second.police_alert_id
    assert len(mgr.list_police_alerts()) == 1


# ----------------------------------------------------------------------------
# Test G — Invalid Case Rejection
# ----------------------------------------------------------------------------
def test_g_invalid_case(test_db):
    mgr = PoliceAlertManager(store=test_db)
    with pytest.raises(KeyError):
        mgr.create_police_alert(case_id="CASE-NONEXISTENT-9999", caller_role="BANK_OFFICIAL")


# ----------------------------------------------------------------------------
# Test H — Authorization Role Enforcement
# ----------------------------------------------------------------------------
def test_h_authorization_enforcement(setup_test_case):
    case_id, store = setup_test_case
    mgr = PoliceAlertManager(store=store)

    # 1. Police officer attempting to create alert -> Rejection
    with pytest.raises(PermissionError):
        mgr.create_police_alert(case_id=case_id, caller_role="POLICE_OFFICER")

    # 2. Bank official creating alert -> Allowed
    created = mgr.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL")

    # 3. Bank official trying to acknowledge police alert -> Rejection
    with pytest.raises(PermissionError):
        mgr.acknowledge_police_alert(police_alert_id=created.police_alert_id, caller_role="BANK_OFFICIAL")

    # 4. Police officer acknowledging alert -> Allowed
    ack = mgr.acknowledge_police_alert(police_alert_id=created.police_alert_id, caller_role="POLICE_OFFICER")
    assert ack.alert_status == PoliceAlertStatus.ACKNOWLEDGED


# ----------------------------------------------------------------------------
# Test I — SQLite Persistence Across Restarts
# ----------------------------------------------------------------------------
def test_i_persistence_across_restarts(setup_test_case):
    case_id, store = setup_test_case
    db_path = store.db_path

    mgr1 = PoliceAlertManager(store=store)
    created = mgr1.create_police_alert(case_id=case_id, caller_role="BANK_OFFICIAL")
    mgr1.acknowledge_police_alert(police_alert_id=created.police_alert_id, caller_role="POLICE_OFFICER")
    store.close()

    # Re-open database from disk
    new_store = Store(db_path=db_path)
    mgr2 = PoliceAlertManager(store=new_store)

    reloaded_alert = mgr2.get_police_alert(created.police_alert_id)
    assert reloaded_alert is not None
    assert reloaded_alert["case_id"] == case_id
    assert reloaded_alert["alert_status"] == PoliceAlertStatus.ACKNOWLEDGED

    new_store.close()
