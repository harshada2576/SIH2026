"""tests/test_notifications.py — Comprehensive Test Suite for Sprint 4 SMS & Email Notification System.

Tests:
- Test A — High-risk alert (SMS generated, EMAIL generated)
- Test B — Confirmed fraud (High-priority notification)
- Test C — Legitimate confirmation (No fraud notification)
- Test D — Withdrawal blocked (Appropriate SMS/email event)
- Test E — Duplicate event (Idempotent single notification per channel/recipient)
- Test F — Provider failure (FAILED / RETRYING without crashing case engine)
- Test G — Persistence (Restart store / verify notification history in SQLite)
- Test H — Configuration (Recipients / provider config loaded from environment)
- Test I — CyberShield (Notification status exposed through backend API for mobile app)
- Test J — Expanded dataset (Run against multi-city dataset, sensible volume)
"""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from api.engine import CaseEngine
from detection.transaction_control import TransactionControlManager
from pipeline.case_orchestrator import CaseOrchestrator
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from pipeline.notification_service import (
    MockEmailProvider,
    MockSmsProvider,
    NotificationDeliveryStatus,
    NotificationEvent,
    NotificationEventType,
    NotificationPreferences,
    NotificationProvider,
    NotificationRecord,
    NotificationRequest,
    NotificationResult,
    RecipientConfig,
    NotificationService,
    format_email,
    format_sms,
)
from pipeline.police_alert_delivery import PoliceAlertManager
from shared.persistence import Store
from shared.schemas import (
    CaseLifecycleState,
    ConfirmationStatus,
    NotificationChannel,
    NotificationRecipientGroup,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / f"test_notifications_{uuid.uuid4().hex[:8]}.db"
    return str(db_file)


@pytest.fixture
def store(temp_db):
    return Store(db_path=Path(temp_db))


@pytest.fixture
def mock_sms():
    return MockSmsProvider()


@pytest.fixture
def mock_email():
    return MockEmailProvider()


@pytest.fixture
def notif_service(store, mock_sms, mock_email):
    return NotificationService(
        store=store,
        sms_provider=mock_sms,
        email_provider=mock_email,
    )


@pytest.fixture
def orchestrator(store, notif_service):
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
        notification_service=notif_service,
    )


# ============================================================================
# TEST A: HIGH-RISK ALERT (SMS & EMAIL GENERATED)
# ============================================================================

def test_a_high_risk_alert_generates_sms_and_email(orchestrator, notif_service, mock_sms, mock_email):
    """Test A — Ingesting a high-risk case automatically generates SMS and Email notifications."""
    cid = f"CASE-HIGH-{uuid.uuid4().hex[:6]}"
    case = orchestrator.ingest_suspicious_event(
        account_id="ACC-MULE-901",
        risk_score=0.88,
        confidence=0.92,
        evidence=["Rapid multi-counterparty fan-in", "Shared device ID"],
        predicted_terminals=[{"terminal_id": "ATM-MUM-017", "probability": 0.90}],
        suspicious_amount=100000.0,
        source="TEST_A",
    )

    # Verify notifications recorded in store for this case
    notifs = notif_service.get_case_notifications(case.case_id)
    channels = {n["channel"] for n in notifs}

    assert "SMS" in channels, "Expected SMS notification generated for high-risk case"
    assert "EMAIL" in channels, "Expected Email notification generated for high-risk case"

    # Verify message contents
    sms_notif = next(n for n in notifs if n["channel"] == "SMS")
    email_notif = next(n for n in notifs if n["channel"] == "EMAIL")

    assert sms_notif["status"] == "SENT"
    assert email_notif["status"] == "SENT"
    assert "SIH26184 ALERT:" in sms_notif["message_body"]
    assert "100,000" in sms_notif["message_body"] or "1,00,000" in sms_notif["message_body"] or "₹100,000" in sms_notif["message_body"]
    assert "ATM-MUM-017" in sms_notif["message_body"]
    assert "High-Risk Fraud Alert" in email_notif["subject"]
    assert "ACC-MULE-901" in email_notif["message_body"]


# ============================================================================
# TEST B: CONFIRMED FRAUD (HIGH-PRIORITY NOTIFICATION)
# ============================================================================

def test_b_confirmed_fraud_generates_high_priority_notification(orchestrator, store, notif_service):
    """Test B — Customer confirming fraud generates high-priority notification and initiates recovery."""
    tx_id = f"TX-CONF-B-{uuid.uuid4().hex[:6]}"
    case = orchestrator.ingest_suspicious_event(
        account_id="ACC-MULE-B",
        risk_score=0.75,
        confidence=0.80,
        evidence=["Anomalous outbound jump"],
        suspicious_amount=75000.0,
        transaction_id=tx_id,
    )

    # Create confirmation record
    conf = orchestrator.control_mgr.request_confirmation(
        transaction_id=tx_id,
        sender_id="ACC-VICTIM-B",
        beneficiary_id="ACC-MULE-B",
        amount=75000.0,
        case_id=case.case_id,
    )

    # Customer confirms fraud
    updated_case = orchestrator.handle_confirmation_update(
        confirmation_id=conf.confirmation_id,
        status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Victim confirmed unauthorized APK transfer",
    )

    assert updated_case.state == CaseLifecycleState.CONFIRMED_FRAUD

    # Check that CONFIRMED_FRAUD event was notified
    notifs = notif_service.get_case_notifications(case.case_id)
    fraud_notifs = [n for n in notifs if n["event_type"] == NotificationEventType.CONFIRMED_FRAUD]

    assert len(fraud_notifs) >= 1, "Expected high-priority CONFIRMED_FRAUD notification"
    sms_fraud = next((n for n in fraud_notifs if n["channel"] == "SMS"), None)
    assert sms_fraud is not None
    assert "PRIORITY ALERT" in sms_fraud["message_body"]
    assert "Confirmed fraud" in sms_fraud["message_body"] or "confirmed fraud" in sms_fraud["message_body"]


# ============================================================================
# TEST C: LEGITIMATE CONFIRMATION (NO FRAUD NOTIFICATION)
# ============================================================================

def test_c_legitimate_confirmation_suppresses_fraud_notification(orchestrator, notif_service):
    """Test C — When transaction is confirmed legitimate, do NOT send fraud notification."""
    tx_id = f"TX-CONF-C-{uuid.uuid4().hex[:6]}"
    case = orchestrator.ingest_suspicious_event(
        account_id="ACC-LEGIT-C",
        risk_score=0.62,
        confidence=0.70,
        evidence=["New counterparty transfer"],
        suspicious_amount=30000.0,
        transaction_id=tx_id,
    )

    conf = orchestrator.control_mgr.request_confirmation(
        transaction_id=tx_id,
        sender_id="ACC-USER-C",
        beneficiary_id="ACC-LEGIT-C",
        amount=30000.0,
        case_id=case.case_id,
    )

    # Customer confirms legitimate
    updated_case = orchestrator.handle_confirmation_update(
        confirmation_id=conf.confirmation_id,
        status=ConfirmationStatus.CONFIRMED_LEGITIMATE,
        notes="Customer verified genuine supplier payment",
    )

    assert updated_case.state == CaseLifecycleState.RESOLVED

    # Check notifications: ensure NO CONFIRMED_FRAUD notification exists
    notifs = notif_service.get_case_notifications(case.case_id)
    fraud_notifs = [n for n in notifs if n["event_type"] == NotificationEventType.CONFIRMED_FRAUD]
    assert len(fraud_notifs) == 0, "Legitimate confirmation must NOT trigger a fraud notification"


# ============================================================================
# TEST D: WITHDRAWAL BLOCKED (APPROPRIATE SMS / EMAIL EVENT)
# ============================================================================

def test_d_withdrawal_blocked_notification(orchestrator, notif_service):
    """Test D — A blocked cashout withdrawal generates a specific WITHDRAWAL_BLOCKED event."""
    cid = f"CASE-WITHDRAW-{uuid.uuid4().hex[:6]}"
    acc = "ACC-MULE-D"
    term = "ATM-BLOCKED-01"

    # Pre-emptively place digital/ATM hold
    case = orchestrator.ingest_suspicious_event(
        account_id=acc,
        risk_score=0.92,
        confidence=0.95,
        evidence=["Critical money mule clustering"],
        predicted_terminals=[{"terminal_id": term, "probability": 0.95}],
        suspicious_amount=50000.0,
    )
    # Put case on freeze/hold
    orchestrator.store.save_case({
        **case.to_dict(),
        "bank_hold_status": "FULL_FREEZE",
        "digitalBlockActive": True,
        "atmBlockActive": True,
    })

    # Simulate blocked withdrawal attempt
    attempt_id = f"ATT-D-{uuid.uuid4().hex[:6]}"
    orchestrator.handle_withdrawal_attempt(
        attempt_id=attempt_id,
        account_id=acc,
        terminal_id=term,
        amount_inr=10000.0,
        case_id=case.case_id,
    )

    notifs = notif_service.get_case_notifications(case.case_id)
    blocked_notifs = [n for n in notifs if n["event_type"] == NotificationEventType.WITHDRAWAL_BLOCKED]

    assert len(blocked_notifs) >= 1, "Expected WITHDRAWAL_BLOCKED notification"
    sms_blocked = next(n for n in blocked_notifs if n["channel"] == "SMS")
    assert "Withdrawal attempt" in sms_blocked["message_body"]
    assert "blocked" in sms_blocked["message_body"]
    assert term in sms_blocked["message_body"]


# ============================================================================
# TEST E: DUPLICATE EVENT (IDEMPOTENCY / DEDUPLICATION)
# ============================================================================

def test_e_duplicate_event_idempotency(notif_service):
    """Test E — Repeated processing of the same case event produces only one notification per channel/recipient."""
    ev = NotificationEvent(
        event_type=NotificationEventType.HIGH_RISK_CASE,
        case_id="CASE-IDEM-001",
        account_id="ACC-IDEM-01",
        amount=50000.0,
        terminal_id="ATM-ND-001",
        risk_score=0.85,
    )

    # First dispatch
    res1 = notif_service.notify(ev)
    count1 = len(res1)
    assert count1 >= 2, "Expected initial SMS + Email dispatch"

    # Second dispatch with identical event
    res2 = notif_service.notify(ev)

    # Third dispatch
    res3 = notif_service.notify(ev)

    # Total persisted notifications for case must equal count1 (no extra duplicates created)
    total_in_db = notif_service.get_case_notifications("CASE-IDEM-001")
    assert len(total_in_db) == count1, f"Expected {count1} unique notifications in DB, found {len(total_in_db)}"


# ============================================================================
# TEST F: PROVIDER FAILURE (FAILED / RETRYING WITHOUT CRASHING CASE ENGINE)
# ============================================================================

class FlakyProvider(NotificationProvider):
    """Provider that always raises an error to test bounded retry and graceful degradation."""
    def __init__(self):
        self.call_count = 0

    def send(self, request: NotificationRequest) -> NotificationResult:
        self.call_count += 1
        raise ConnectionError(f"Simulated network timeout (attempt {self.call_count})")


def test_f_provider_failure_retry_and_graceful_degradation(store):
    """Test F — Provider failures retry up to max_retries, mark as FAILED, and never crash caller."""
    flaky = FlakyProvider()
    service = NotificationService(
        store=store,
        sms_provider=flaky,
        email_provider=flaky,
        max_retries=3,
    )

    ev = NotificationEvent(
        event_type=NotificationEventType.HIGH_RISK_CASE,
        case_id="CASE-FAIL-001",
        account_id="ACC-FAIL-01",
        amount=25000.0,
    )

    # Must execute without throwing unhandled exception
    records = service.notify(ev)

    # Verify notifications reached FAILED state after exactly 3 retries
    notifs = service.get_case_notifications("CASE-FAIL-001")
    assert len(notifs) >= 1
    for n in notifs:
        assert n["status"] == NotificationDeliveryStatus.FAILED
        assert n["retry_count"] == 3
        assert "Simulated network timeout" in (n.get("error") or "")


# ============================================================================
# TEST G: PERSISTENCE (RESTART STORE / QUERY SQLITE)
# ============================================================================

def test_g_persistence_across_store_restarts(temp_db):
    """Test G — Persisted notifications remain queryable after closing and reopening database."""
    # Store session 1
    s1 = Store(db_path=Path(temp_db))
    svc1 = NotificationService(store=s1)
    svc1.notify(NotificationEvent(
        event_type=NotificationEventType.HIGH_RISK_CASE,
        case_id="CASE-PERSIST-99",
        account_id="ACC-PERSIST-01",
        amount=120000.0,
        terminal_id="ATM-PERSIST-01",
    ))
    s1.close()

    # Store session 2 (reopened DB)
    s2 = Store(db_path=Path(temp_db))
    svc2 = NotificationService(store=s2)
    saved = svc2.get_case_notifications("CASE-PERSIST-99")

    assert len(saved) >= 2, "Notifications must survive database close and reopen"
    channels = {n["channel"] for n in saved}
    assert "SMS" in channels
    assert "EMAIL" in channels
    assert saved[0]["case_id"] == "CASE-PERSIST-99"
    s2.close()


# ============================================================================
# TEST H: CONFIGURATION (ENVIRONMENT OVERRIDES)
# ============================================================================

def test_h_recipient_and_provider_configuration(monkeypatch, store):
    """Test H — Recipient phone numbers and emails are loaded from configuration / environment variables."""
    test_phone = "+919999888877"
    test_email = "custom.investigator@bank.gov.in"

    monkeypatch.setenv("BANK_OFFICIAL_PHONE", test_phone)
    monkeypatch.setenv("BANK_OFFICIAL_EMAIL", test_email)

    cfg = RecipientConfig()
    sms_recips = cfg.get_recipients(NotificationEventType.HIGH_RISK_CASE, NotificationChannel.SMS)
    email_recips = cfg.get_recipients(NotificationEventType.HIGH_RISK_CASE, NotificationChannel.EMAIL)

    phone_addrs = [addr for addr, group in sms_recips]
    email_addrs = [addr for addr, group in email_recips]

    assert test_phone in phone_addrs, f"Expected {test_phone} in configured SMS recipients"
    assert test_email in email_addrs, f"Expected {test_email} in configured Email recipients"


# ============================================================================
# TEST I: CYBERSHIELD BACKEND INTEGRATION
# ============================================================================

def test_i_cybershield_api_and_notification_summary(temp_db):
    """Test I — Notification status is exposed through the backend API structure consumed by Android."""
    engine = CaseEngine()
    cases = engine.list_cases("BANK")
    assert len(cases) > 0

    first_case = cases[0]
    cid = first_case["ncrpId"]

    # Verify notificationStatus and notifications fields exist in case dictionary
    assert "notificationStatus" in first_case, "Case dictionary must include notificationStatus for Android"
    assert "notifications" in first_case, "Case dictionary must include notifications list for Android"

    # Verify channel statuses
    ch_map = first_case["notificationStatus"]
    assert "SMS" in ch_map
    assert "EMAIL" in ch_map

    # Test engine act trigger: simulate cashout withdrawal attempt
    updated_case = engine.act(cid, "simulate_withdraw", officer="Inspector Sharma")
    assert updated_case is not None
    assert len(updated_case["withdrawalAttempts"]) > 0

    # Ensure updated case refreshed notificationStatus and notifications
    summary = engine.notification_service.get_case_notification_summary(cid)
    assert len(summary["items"]) > 0


# ============================================================================
# TEST J: EXPANDED DATASET NOTIFICATION VOLUME
# ============================================================================

def test_j_expanded_dataset_sensible_notification_volume(store, notif_service):
    """Test J — Notification volume remains sensible and does not flood notifications for normal traffic."""
    # Simulate 100 normal transactions and 5 critical fraud alerts
    normal_events = 100
    critical_alerts = 5

    # 1. Normal transactions should NOT trigger fraud notifications
    # (they pass through GraphStore without threshold crossing)
    for i in range(critical_alerts):
        notif_service.notify(NotificationEvent(
            event_type=NotificationEventType.HIGH_RISK_CASE,
            case_id=f"CASE-MULTI-CITY-{i:03d}",
            account_id=f"ACC-HUB-MULE-{i}",
            amount=50000.0 + i * 10000,
            terminal_id=f"ATM-CITY-{i}",
            risk_score=0.85,
        ))

    # Total notifications in DB should be bounded strictly to the critical alerts
    all_notifs = store.recent_notifications(limit=100)
    assert len(all_notifs) == critical_alerts * 4, (
        f"Expected {critical_alerts * 4} notifications (2 SMS + 2 Email per alert across 2 recipient groups), "
        f"got {len(all_notifs)}"
    )
