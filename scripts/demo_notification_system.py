"""scripts/demo_notification_system.py — Operational Demo for Sprint 4 SMS & Email Notifications.

Executes the complete operational lifecycle:
1. High-risk fraud detected -> Case created in CaseOrchestrator
2. SMS generated & delivered (simulated or real) to configured Bank Official / Security Team
3. Structured Email generated & delivered with plain + HTML formatting
4. CyberShield mobile query -> Inspects case with authoritative notification status
5. Cash-out withdrawal attempt detected at physical ATM
6. Withdrawal blocked -> WITHDRAWAL_BLOCKED SMS & Email alerts dispatched
7. Customer confirmation workflow -> High-priority CONFIRMED_FRAUD notification
8. Bank official reviews evidence & clicks ALERT POLICE -> Police alert + escalation notice
9. Full audit history and delivery log verification

Run:
  python -m scripts.demo_notification_system
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.engine import CaseEngine
from detection.transaction_control import TransactionControlManager
from pipeline.case_orchestrator import CaseOrchestrator
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from pipeline.notification_service import (
    NotificationEvent,
    NotificationEventType,
    NotificationService,
)
from pipeline.police_alert_delivery import PoliceAlertManager
from shared.persistence import Store
from shared.schemas import CaseLifecycleState, ConfirmationStatus, PoliceAlertStatus


def banner(title: str) -> None:
    line = "=" * 80
    print(f"\n{line}\n  {title}\n{line}")


def step(num: int, title: str) -> None:
    print(f"\n[STEP {num:02d}] {title}")
    print("-" * 75)


def run_demo():
    banner("SIH26184: SPRINT 4 - SMS & EMAIL NOTIFICATION SUBSYSTEM DEMO")

    mode = os.environ.get("NOTIFICATION_MODE", "mock").upper()
    sms_mode = "REAL" if os.environ.get("SMS_GATEWAY_URL") else "SIMULATED"
    email_mode = "REAL" if os.environ.get("SMTP_HOST") else "SIMULATED"

    print(f"  Configuration:")
    print(f"    - Subsystem Mode: {mode}")
    print(f"    - SMS Delivery:   {sms_mode}")
    print(f"    - Email Delivery: {email_mode}")
    print(f"    - Bank Official:  {os.environ.get('BANK_OFFICIAL_PHONE', '+919876543210')} | {os.environ.get('BANK_OFFICIAL_EMAIL', 'duty.officer@cybershield.bank')}")
    print(f"    - Security Team:  {os.environ.get('SECURITY_TEAM_PHONE', '+919876543211')} | {os.environ.get('SECURITY_TEAM_EMAIL', 'soc.alerts@cybershield.bank')}")

    # Initialize store and orchestrator
    store = Store()
    ctrl = TransactionControlManager(store=store)
    trace = FundTraceabilityEngine(store=store)
    geo = WithdrawalGeoIntelligence(store=store)
    pol = PoliceAlertManager(store=store, trace_engine=trace, geo_intel=geo)
    notif = NotificationService(store=store)
    orchestrator = CaseOrchestrator(
        store=store,
        control_mgr=ctrl,
        trace_engine=trace,
        geo_intel=geo,
        police_mgr=pol,
        notification_service=notif,
    )

    victim_acc = f"ACC-VICTIM-{uuid.uuid4().hex[:4].upper()}"
    mule_acc = f"ACC-MULE-L1-{uuid.uuid4().hex[:4].upper()}"
    target_atm = "ATM-MUM-017"
    tx_id = f"TX-SPRINT4-{uuid.uuid4().hex[:6].upper()}"
    case_amount = 100000.0

    # Step 1: Detection Engine Flag -> Case Creation & Notifications
    step(1, "DETECTION ENGINE FLAGS HIGH-RISK FRAUD (CASE CREATED)")
    case = orchestrator.ingest_suspicious_event(
        account_id=mule_acc,
        risk_score=0.89,
        confidence=0.94,
        evidence=[
            "High velocity layering chain (Rs. 1,00,000 across 3 hops in 4 minutes)",
            "Shared device fingerprint with known cyber syndicate",
            "High affinity targeting for ATM-MUM-017 cash egress",
        ],
        predicted_terminals=[{"terminal_id": target_atm, "probability": 0.92}],
        suspicious_amount=case_amount,
        transaction_id=tx_id,
        source="DETECTION_ENGINE",
    )
    cid = case.case_id
    print(f"  [+] Investigation Case Created: {cid}")
    print(f"  [+] Flagged Account: {mule_acc} | Amount: Rs. {case_amount:,.2f} | Risk Band: {case.band}")

    # Inspect generated notifications
    case_notifs = notif.get_case_notifications(cid)
    print(f"  [+] Outbound Notifications Generated: {len(case_notifs)}")
    for n in case_notifs:
        sim_tag = "[SIMULATED]" if n.get("is_simulated") else "[REAL]"
        print(f"      * {sim_tag} {n['channel']:<5} -> {n['recipient']} ({n['recipient_group']}): Status {n['status']}")
        if n['channel'] == "SMS":
            print(f"        Body: {n['message_body'].replace(chr(10), ' ')}")

    # Step 2: CyberShield Mobile View Inspection
    step(2, "CYBERSHIELD MOBILE APP SYNCHRONIZATION")
    summary = notif.get_case_notification_summary(cid)
    print(f"  [+] CyberShield Case Detail Delivery Card Status:")
    print(f"      - SMS Channel:   {summary['channels']['SMS']['status']} ({'Simulated' if summary['channels']['SMS']['is_simulated'] else 'Live'})")
    print(f"      - Email Channel: {summary['channels']['EMAIL']['status']} ({'Simulated' if summary['channels']['EMAIL']['is_simulated'] else 'Live'})")
    print(f"      - Total Dispatched Items Recorded: {len(summary['items'])}")

    # Step 3: Cashout Withdrawal Interception & Block
    step(3, "CASHOUT WITHDRAWAL ATTEMPT DETECTED & INTERCEPTED AT ATM")
    # Activate digital & physical ATM block
    store.save_case({
        **case.to_dict(),
        "bank_hold_status": "FULL_FREEZE",
        "digitalBlockActive": True,
        "atmBlockActive": True,
    })

    att_id = f"ATT-MUM-{uuid.uuid4().hex[:6].upper()}"
    orchestrator.handle_withdrawal_attempt(
        attempt_id=att_id,
        account_id=mule_acc,
        terminal_id=target_atm,
        amount_inr=10000.0,
        case_id=cid,
    )
    print(f"  [+] Withdrawal Attempt at {target_atm} for Rs. 10,000 BLOCKED.")
    
    # Check blocked withdrawal notification
    blocked_notifs = [n for n in notif.get_case_notifications(cid) if n["event_type"] == NotificationEventType.WITHDRAWAL_BLOCKED]
    print(f"  [+] Withdrawal Block Notifications Dispatched: {len(blocked_notifs)}")
    for n in blocked_notifs:
        sim_tag = "[SIMULATED]" if n.get("is_simulated") else "[REAL]"
        print(f"      * {sim_tag} {n['channel']:<5} -> {n['recipient']}: {n['message_body'].splitlines()[0]}")

    # Step 4: Customer Confirmation Workflow -> CONFIRMED_FRAUD
    step(4, "CUSTOMER CONFIRMATION WORKFLOW (CONFIRMED_FRAUD)")
    conf = ctrl.request_confirmation(
        transaction_id=tx_id,
        sender_id=victim_acc,
        beneficiary_id=mule_acc,
        amount=case_amount,
        case_id=cid,
    )
    print(f"  [+] Issued Customer Confirmation: {conf.confirmation_id}")
    
    # Customer responds CONFIRMED_FRAUD
    orchestrator.handle_confirmation_update(
        confirmation_id=conf.confirmation_id,
        status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Victim confirmed unauthorized APK remote-access theft",
    )
    fraud_notifs = [n for n in notif.get_case_notifications(cid) if n["event_type"] == NotificationEventType.CONFIRMED_FRAUD]
    print(f"  [+] Case Escalated to CONFIRMED_FRAUD.")
    print(f"  [+] Priority Fraud Notifications Dispatched: {len(fraud_notifs)}")
    for n in fraud_notifs:
        sim_tag = "[SIMULATED]" if n.get("is_simulated") else "[REAL]"
        print(f"      * {sim_tag} {n['channel']:<5} -> {n['recipient']}: {n['message_body'].splitlines()[0]}")

    # Step 5: Bank Official Clicks 'ALERT POLICE' in CyberShield
    step(5, "BANK OFFICIAL CLICKS 'ALERT POLICE' IN CYBERSHIELD")
    pol_res = orchestrator.trigger_police_alert(
        case_id=cid,
        actor_role="BANK_OFFICIAL",
        source="CyberShield Mobile Dashboard",
    )
    p_alert = pol_res["police_alert"]
    print(f"  [+] Police Alert Package Created: {p_alert['police_alert_id']}")
    print(f"  [+] Destination: Nearest Field Patrol to {target_atm}")

    pol_notifs = [n for n in notif.get_case_notifications(cid) if n["event_type"] == NotificationEventType.POLICE_ALERT_SENT]
    print(f"  [+] Internal Police Escalation Notice Dispatched to Bank/Security Team: {len(pol_notifs)}")
    for n in pol_notifs:
        sim_tag = "[SIMULATED]" if n.get("is_simulated") else "[REAL]"
        print(f"      * {sim_tag} {n['channel']:<5} -> {n['recipient']}: {n['message_body'].splitlines()[0]}")

    # Step 6: Final Verification & Audit Trail Summary
    step(6, "FINAL VERIFICATION & AUDIT TRAIL")
    all_notifs = notif.get_case_notifications(cid)
    print(f"  [+] Total Persistent Notifications in SQLite for Case {cid}: {len(all_notifs)}")
    by_event: dict[str, int] = {}
    for n in all_notifs:
        by_event[n["event_type"]] = by_event.get(n["event_type"], 0) + 1
    for ev_name, count in by_event.items():
        print(f"      - {ev_name:<30}: {count} deliveries")

    banner("DEMO SCENARIO COMPLETE: ALL NOTIFICATIONS DELIVERED & SYNCHRONIZED")
    print(f"  Summary:")
    print(f"    - SMS Delivery:    {sms_mode}")
    print(f"    - Email Delivery:  {email_mode}")
    print(f"    - Mobile API:      LOCAL LAN COMPATIBLE (0.0.0.0:5003)")
    print(f"    - Persistence:     SQLite (cybershield.db -> notifications table)\n")


if __name__ == "__main__":
    run_demo()
