"""tests/test_case_orchestration.py — Unit tests for Part 6 Case Orchestration & Escalation.

Tests:
A — Suspicious case creation / update
B — Multiple suspicious events (accumulation)
C — Pending confirmation monitoring state
D — Confirmed legitimate resolution
E — Confirmed fraud escalation and recovery linkage
F — Withdrawal attempt recording in case timeline
G — Repeated account/ATM activity priority escalation
H — Complaint / FIR attachment (POST_COMPLAINT_ESCALATED)
I — Police alert eligibility evaluation
J — Bank official ALERT POLICE trigger and linkage
K — Idempotency and deduplication across repeated events
L — Complete 10-stage investigation lifecycle
"""
import os
import pytest
from datetime import datetime, timezone
from shared.persistence import Store
from detection.transaction_control import TransactionControlManager
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from pipeline.police_alert_delivery import PoliceAlertManager
from pipeline.case_orchestrator import CaseOrchestrator
from shared.schemas import CaseLifecycleState, ConfirmationStatus, PoliceAlertStatus


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test_orchestrator.db")
    return Store(db_path=db_path)


@pytest.fixture
def orchestrator(store):
    ctrl = TransactionControlManager(store=store)
    trace = FundTraceabilityEngine(store=store)
    geo = WithdrawalGeoIntelligence(store=store)
    pol = PoliceAlertManager(store=store, trace_engine=trace, geo_intel=geo)
    return CaseOrchestrator(
        store=store,
        control_mgr=ctrl,
        trace_engine=trace,
        geo_intel=geo,
        police_mgr=pol,
    )


# ----------------------------------------------------------------------------
# Test A — Suspicious Case Creation
# ----------------------------------------------------------------------------
def test_a_suspicious_case_creation(orchestrator):
    case_rec = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-A",
        risk_score=0.65,
        confidence=0.80,
        evidence=["Suspicious inbound transfer from unknown account"],
        predicted_terminals=["ATM-101"],
        suspicious_amount=50000.0,
        transaction_id="TX-1001",
    )
    assert case_rec.case_id == "CASE-TX-1001"
    assert case_rec.flagged_account_id == "ACC-TEST-A"
    assert case_rec.state == CaseLifecycleState.PRE_COMPLAINT_INTERVENTION
    assert case_rec.priority == "HIGH"
    assert case_rec.police_alert_eligible is False

    # Check timeline event creation
    tl = orchestrator.get_case_timeline(case_rec.case_id)
    assert len(tl) >= 1
    assert tl[0]["event_type"] == "CASE_INITIALIZED"


# ----------------------------------------------------------------------------
# Test B — Multiple Suspicious Events (Accumulation)
# ----------------------------------------------------------------------------
def test_b_multiple_suspicious_events_accumulation(orchestrator):
    c1 = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-B",
        risk_score=0.55,
        confidence=0.70,
        evidence=["Event 1: Rapid forwarding"],
        suspicious_amount=30000.0,
        transaction_id="TX-2001",
    )
    assert c1.priority == "MEDIUM"

    # Second event for same account accumulated into existing active case
    c2 = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-B",
        risk_score=0.85,
        confidence=0.92,
        evidence=["Event 2: Shared device login across 3 accounts"],
        suspicious_amount=70000.0,
        transaction_id="TX-2002",
    )

    assert c2.case_id == c1.case_id
    assert c2.risk_score == 0.85
    assert c2.priority == "CRITICAL"
    assert c2.police_alert_eligible is True
    assert len(c2.evidence) == 2

    tl = orchestrator.get_case_timeline(c1.case_id)
    event_types = [t["event_type"] for t in tl]
    assert "SUSPICIOUS_EVENT_ACCUMULATED" in event_types


# ----------------------------------------------------------------------------
# Test C — Pending Confirmation State
# ----------------------------------------------------------------------------
def test_c_pending_confirmation(orchestrator):
    case_rec = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-C",
        risk_score=0.75,
        confidence=0.85,
        evidence=["Anomalous high-value transfer"],
        suspicious_amount=100000.0,
        transaction_id="TX-3001",
    )

    conf_rec = orchestrator.control_mgr.request_confirmation(
        transaction_id="TX-3001",
        sender_id="ACC-VICTIM-C",
        beneficiary_id="ACC-TEST-C",
        amount=100000.0,
        reason="High-value transfer verification",
        case_id=case_rec.case_id,
    )

    assert conf_rec.status == ConfirmationStatus.PENDING_CONFIRMATION

    # Downstream online transfer evaluation: allowed & monitored
    decision = orchestrator.control_mgr.evaluate_transaction_control(
        transaction_id="TX-3002",
        from_account="ACC-TEST-C",
        to_account="ACC-DOWNSTREAM-C",
        amount=50000.0,
        channel_or_type="UPI",
    )
    assert decision.action in ("MONITOR", "ALLOW_MONITORED", "ALLOW")

    # Suspicious cashout evaluation: blocked/restricted
    cashout_decision = orchestrator.control_mgr.evaluate_transaction_control(
        transaction_id="TX-3003",
        from_account="ACC-TEST-C",
        to_account="NONE",
        amount=50000.0,
        channel_or_type="ATM",
    )
    assert cashout_decision.action in ("RESTRICT", "BLOCK_CASHOUT", "PROVISIONAL_HOLD", "BLOCK")


# ----------------------------------------------------------------------------
# Test D — Confirmed Legitimate Resolution
# ----------------------------------------------------------------------------
def test_d_confirmed_legitimate_resolution(orchestrator):
    case_rec = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-D",
        risk_score=0.70,
        confidence=0.80,
        evidence=["Unusual transaction size"],
        suspicious_amount=40000.0,
        transaction_id="TX-4001",
    )

    conf_rec = orchestrator.control_mgr.request_confirmation(
        transaction_id="TX-4001",
        sender_id="ACC-VICTIM-D",
        beneficiary_id="ACC-TEST-D",
        amount=40000.0,
        case_id=case_rec.case_id,
    )

    # Customer responds LEGITIMATE
    orchestrator.control_mgr.submit_confirmation_response(
        confirmation_id=conf_rec.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_LEGITIMATE,
        notes="Customer verified payment for salary bonus",
    )

    # Handle orchestration update
    updated_case = orchestrator.handle_confirmation_update(
        confirmation_id=conf_rec.confirmation_id,
        status=ConfirmationStatus.CONFIRMED_LEGITIMATE,
        notes="Customer verified payment for salary bonus",
    )

    assert updated_case.state == CaseLifecycleState.RESOLVED
    assert updated_case.priority == "LOW"
    assert updated_case.police_alert_eligible is False
    assert "CONFIRMED_LEGITIMATE" in updated_case.resolution_reason


# ----------------------------------------------------------------------------
# Test E — Confirmed Fraud Escalation & Recovery Linkage
# ----------------------------------------------------------------------------
def test_e_confirmed_fraud_escalation(orchestrator):
    case_rec = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-E",
        risk_score=0.88,
        confidence=0.95,
        evidence=["Suspicious multi-hop forward"],
        suspicious_amount=150000.0,
        transaction_id="TX-5001",
        chain_id="CHAIN-5001",
    )

    conf_rec = orchestrator.control_mgr.request_confirmation(
        transaction_id="TX-5001",
        sender_id="ACC-VICTIM-E",
        beneficiary_id="ACC-TEST-E",
        amount=150000.0,
        case_id=case_rec.case_id,
    )

    # Customer responds FRAUD
    orchestrator.control_mgr.submit_confirmation_response(
        confirmation_id=conf_rec.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Customer declared unauthorized SIM swap cyber fraud",
    )

    updated_case = orchestrator.handle_confirmation_update(
        confirmation_id=conf_rec.confirmation_id,
        status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Unauthorized SIM swap cyber fraud",
    )

    assert updated_case.state == CaseLifecycleState.CONFIRMED_FRAUD
    assert updated_case.priority == "CRITICAL"
    assert updated_case.police_alert_eligible is True
    assert updated_case.recovery_case_id is not None
    assert "TX-5001" in updated_case.recovery_case_id


# ----------------------------------------------------------------------------
# Test F — Withdrawal Attempt Recording in Timeline
# ----------------------------------------------------------------------------
def test_f_withdrawal_attempt_timeline(orchestrator):
    case_rec = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-F",
        risk_score=0.72,
        confidence=0.85,
        evidence=["Rapid forwarding to cashout mule account"],
        suspicious_amount=25000.0,
        transaction_id="TX-6001",
    )

    res_case = orchestrator.handle_withdrawal_attempt(
        attempt_id="ATT-6001",
        account_id="ACC-TEST-F",
        terminal_id="ATM-DELHI-09",
        amount_inr=25000.0,
        case_id=case_rec.case_id,
    )

    assert res_case.state == CaseLifecycleState.CASHOUT_ATTEMPT_DETECTED
    tl = orchestrator.get_case_timeline(case_rec.case_id)
    event_types = [t["event_type"] for t in tl]
    assert "CASHOUT_ATTEMPT_RECORDED" in event_types


# ----------------------------------------------------------------------------
# Test G — Repeated Account / ATM Activity Priority Escalation
# ----------------------------------------------------------------------------
def test_g_repeated_atm_activity_escalation(orchestrator):
    case_rec = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-G",
        risk_score=0.60,
        confidence=0.75,
        evidence=["Initial low suspicious activity"],
        suspicious_amount=10000.0,
        transaction_id="TX-7001",
    )

    # 3 repeated withdrawal attempts at same ATM
    for i in range(3):
        orchestrator.handle_withdrawal_attempt(
            attempt_id=f"ATT-700{i}",
            account_id="ACC-TEST-G",
            terminal_id="ATM-PERSISTENT-01",
            amount_inr=10000.0,
            case_id=case_rec.case_id,
        )

    c_details = orchestrator.get_case_details(case_rec.case_id)
    assert c_details["priority"] in ("HIGH", "CRITICAL")
    assert any("PERSISTENT_TERMINAL_RISK" in ev for ev in c_details["evidence"])


# ----------------------------------------------------------------------------
# Test H — Formal Complaint / FIR Escalation
# ----------------------------------------------------------------------------
def test_h_complaint_fir_attachment(orchestrator):
    case_rec = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-H",
        risk_score=0.65,
        confidence=0.80,
        evidence=["Suspicious activity"],
        suspicious_amount=80000.0,
        transaction_id="TX-8001",
    )

    updated = orchestrator.attach_complaint_fir(
        case_id=case_rec.case_id,
        complaint_id="NCRP-2026-889911",
        fir_number="FIR-DEL-2026-00445",
        victim_account="ACC-VICTIM-H",
        reported_loss=80000.0,
    )

    assert updated.state == CaseLifecycleState.POST_COMPLAINT_ESCALATED
    assert updated.priority == "CRITICAL"
    assert updated.police_alert_eligible is True
    assert updated.fir_number == "FIR-DEL-2026-00445"

    tl = orchestrator.get_case_timeline(case_rec.case_id)
    event_types = [t["event_type"] for t in tl]
    assert "FORMAL_COMPLAINT_FIR_ATTACHED" in event_types


# ----------------------------------------------------------------------------
# Test I — Police Eligibility Evaluation
# ----------------------------------------------------------------------------
def test_i_police_eligibility_evaluation(orchestrator):
    # Low/Medium risk suspicious case -> not eligible for police alert
    c_med = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-I1",
        risk_score=0.55,
        confidence=0.70,
        evidence=["Single suspicious transfer"],
        suspicious_amount=15000.0,
        transaction_id="TX-9001",
    )
    assert c_med.police_alert_eligible is False

    # High risk with cashout attempt -> eligible
    c_high = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-I2",
        risk_score=0.85,
        confidence=0.90,
        evidence=["High velocity layering"],
        suspicious_amount=200000.0,
        transaction_id="TX-9002",
    )
    assert c_high.police_alert_eligible is True


# ----------------------------------------------------------------------------
# Test J — Police Action Trigger & Linkage
# ----------------------------------------------------------------------------
def test_j_police_action_trigger(orchestrator):
    case_rec = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-J",
        risk_score=0.90,
        confidence=0.95,
        evidence=["Confirmed mule account cashout"],
        suspicious_amount=120000.0,
        transaction_id="TX-10001",
    )

    res = orchestrator.trigger_police_alert(
        case_id=case_rec.case_id,
        actor_role="BANK_OFFICIAL",
        source="CyberShield Bank Official Dashboard",
    )

    assert res["status"] == "SUCCESS"
    assert res["case"]["state"] == CaseLifecycleState.POLICE_ALERT_SENT
    assert res["police_alert"]["police_alert_id"].startswith("POL-")

    # Verify police app can retrieve the alert
    pol_alert = orchestrator.police_mgr.get_police_alert(res["police_alert"]["police_alert_id"])
    assert pol_alert is not None
    assert pol_alert["case_id"] == case_rec.case_id


# ----------------------------------------------------------------------------
# Test K — Deduplication & Idempotency
# ----------------------------------------------------------------------------
def test_k_deduplication(orchestrator):
    # Ingest event 1
    c1 = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-K",
        risk_score=0.65,
        confidence=0.75,
        evidence=["Anomaly A"],
        suspicious_amount=50000.0,
        transaction_id="TX-11001",
    )

    # Ingest event 2 for same transaction_id
    c2 = orchestrator.ingest_suspicious_event(
        account_id="ACC-TEST-K",
        risk_score=0.70,
        confidence=0.80,
        evidence=["Anomaly B"],
        suspicious_amount=50000.0,
        transaction_id="TX-11001",
    )

    assert c1.case_id == c2.case_id

    # Check total count of active cases in store
    cases = orchestrator.list_cases(account_id="ACC-TEST-K")
    assert len(cases) == 1


# ----------------------------------------------------------------------------
# Test L — Complete 10-Stage Lifecycle Test
# ----------------------------------------------------------------------------
def test_l_full_investigation_lifecycle(orchestrator):
    # 1. OBSERVED -> SUSPICIOUS -> PRE_COMPLAINT_INTERVENTION
    c1 = orchestrator.ingest_suspicious_event(
        account_id="ACC-LIFECYCLE-MULE",
        risk_score=0.65,
        confidence=0.80,
        evidence=["Anomalous inbound transfer ₹1,00,000"],
        suspicious_amount=100000.0,
        transaction_id="TX-LIFE-001",
        chain_id="CHAIN-LIFE-001",
    )
    cid = c1.case_id
    assert c1.state == CaseLifecycleState.PRE_COMPLAINT_INTERVENTION

    # 2. PENDING_CONFIRMATION (Part 1)
    conf = orchestrator.control_mgr.request_confirmation(
        transaction_id="TX-LIFE-001",
        sender_id="ACC-LIFE-VICTIM",
        beneficiary_id="ACC-LIFECYCLE-MULE",
        amount=100000.0,
        case_id=cid,
    )
    assert conf.status == ConfirmationStatus.PENDING_CONFIRMATION

    # 3. CASHOUT_ATTEMPT_DETECTED (Part 3)
    c3 = orchestrator.handle_withdrawal_attempt(
        attempt_id="ATT-LIFE-01",
        account_id="ACC-LIFECYCLE-MULE",
        terminal_id="ATM-LIFE-DELHI",
        amount_inr=50000.0,
        case_id=cid,
    )
    assert c3.state == CaseLifecycleState.CASHOUT_ATTEMPT_DETECTED

    # 4. CONFIRMED_FRAUD (Part 1 & Part 2 Recovery)
    orchestrator.control_mgr.submit_confirmation_response(
        confirmation_id=conf.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Victim confirmed online banking compromise",
    )
    c4 = orchestrator.handle_confirmation_update(
        confirmation_id=conf.confirmation_id,
        status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Victim confirmed online banking compromise",
    )
    assert c4.state == CaseLifecycleState.CONFIRMED_FRAUD
    assert c4.recovery_case_id is not None

    # 5. POST_COMPLAINT_ESCALATED (Part 4 / NCRP FIR)
    c5 = orchestrator.attach_complaint_fir(
        case_id=cid,
        complaint_id="NCRP-2026-991122",
        fir_number="FIR-DEL-2026-9900",
        victim_account="ACC-LIFE-VICTIM",
        reported_loss=100000.0,
    )
    assert c5.state == CaseLifecycleState.POST_COMPLAINT_ESCALATED

    # 6. POLICE_ALERT_SENT (Part 5 Police Alert)
    res_pol = orchestrator.trigger_police_alert(
        case_id=cid,
        actor_role="BANK_OFFICIAL",
        source="CyberShield Bank Official Dashboard",
    )
    assert res_pol["case"]["state"] == CaseLifecycleState.POLICE_ALERT_SENT
    pol_id = res_pol["police_alert"]["police_alert_id"]

    # 7. UNDER_INVESTIGATION (Part 5 Police Officer Acknowledgment & Status)
    orchestrator.police_mgr.acknowledge_police_alert(
        police_alert_id=pol_id,
        caller_role="POLICE_OFFICER",
        officer_id="INSPECTOR-SHARMA-07",
        notes="Case assigned to Cyber Crime Branch Delhi",
    )
    orchestrator.police_mgr.update_investigation_status(
        police_alert_id=pol_id,
        new_status=PoliceAlertStatus.UNDER_INVESTIGATION,
        caller_role="POLICE_OFFICER",
        officer_id="INSPECTOR-SHARMA-07",
        notes="Mule account frozen across CBS, suspect located near ATM",
    )

    # 8. RESOLVED
    c8 = orchestrator.resolve_case(
        case_id=cid,
        reason="Mule apprehended, funds seized via Part 2 recovery workflow and court order",
        actor_id="BANK_OFFICIAL",
    )
    assert c8.state == CaseLifecycleState.RESOLVED

    # Verify complete timeline events sequence
    timeline = orchestrator.get_case_timeline(cid)
    assert len(timeline) >= 6
    types = [t["event_type"] for t in timeline]
    assert "CASE_INITIALIZED" in types
    assert "CASHOUT_ATTEMPT_RECORDED" in types
    assert "CONFIRMATION_FRAUD_ESCALATED" in types
    assert "FORMAL_COMPLAINT_FIR_ATTACHED" in types
    assert "POLICE_ALERT_DISPATCHED" in types
    assert "CASE_RESOLVED" in types
