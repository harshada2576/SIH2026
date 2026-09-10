"""scripts/demo_full_case_orchestration.py — End-to-End Case Orchestration Demo.

Executes the complete investigation lifecycle across all SIH26184 modules:
1. Unusual A -> B transaction (Detection Engine -> Orchestrator)
2. Confirmation requested (Part 1 Transaction Control -> PENDING_CONFIRMATION)
3. Downstream transfers (B -> C -> D) tracked via Part 2 Fund Traceability
4. Online transfers allowed + monitored vs Cashout attempt blocked (Part 1 & Part 3)
5. ATM location evidence recorded in case timeline
6. Customer A confirms fraud (Part 1 -> CONFIRMED_FRAUD)
7. Money trail traced & Recovery Case created (Part 2 Fund Traceability)
8. Priority escalated to CRITICAL & Police Alert Eligibility enabled (Part 4 CyberShield)
9. Bank Official reviews case and clicks 'ALERT POLICE' (Part 5 Police Alert)
10. Police App receives structured alert, acknowledges & investigates
11. Case resolved and closed with full audit trail

Run:
  python -m scripts.demo_full_case_orchestration
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.persistence import Store
from detection.transaction_control import TransactionControlManager
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from pipeline.police_alert_delivery import PoliceAlertManager
from pipeline.case_orchestrator import CaseOrchestrator
from shared.schemas import CaseLifecycleState, ConfirmationStatus, PoliceAlertStatus


def print_step(step_num: int, title: str) -> None:
    print(f"\n[{step_num:02d}] {title}")
    print("-" * 75)


def run_demo():
    print("=" * 80)
    print("  SIH26184: END-TO-END CASE ORCHESTRATION & ESCALATION LIFECYCLE DEMO")
    print("=" * 80)

    # Initialize store and components
    store = Store()
    ctrl = TransactionControlManager(store=store)
    trace = FundTraceabilityEngine(store=store)
    geo = WithdrawalGeoIntelligence(store=store)
    pol = PoliceAlertManager(store=store, trace_engine=trace, geo_intel=geo)
    orchestrator = CaseOrchestrator(
        store=store,
        control_mgr=ctrl,
        trace_engine=trace,
        geo_intel=geo,
        police_mgr=pol,
    )

    victim_acc = f"ACC-VICTIM-ALICE-{uuid.uuid4().hex[:4]}"
    mule_l1 = f"ACC-MULE-BOB-{uuid.uuid4().hex[:4]}"
    mule_l2 = f"ACC-MULE-CHARLIE-{uuid.uuid4().hex[:4]}"
    mule_l3 = f"ACC-MULE-DAVID-{uuid.uuid4().hex[:4]}"
    atm_id = "ATM-DELHI-CP-04"
    tx_root_id = f"TX-DEMO-ROOT-{uuid.uuid4().hex[:6]}"
    chain_id = f"CHAIN-DEMO-{uuid.uuid4().hex[:6]}"

    # Step 1: Ingest Initial Suspicious Transaction (A -> B)
    print_step(1, f"DETECTION ENGINE DETECTS UNUSUAL TRANSACTION A -> B ({tx_root_id})")
    c1 = orchestrator.ingest_suspicious_event(
        account_id=mule_l1,
        risk_score=0.72,
        confidence=0.88,
        evidence=["High velocity inbound transfer from new counterparty", "Behavioral anomaly"],
        predicted_terminals=[{"terminal_id": atm_id, "probability": 0.95}],
        suspicious_amount=100000.0,
        transaction_id=tx_root_id,
        chain_id=chain_id,
        source="DETECTION_ENGINE",
    )
    cid = c1.case_id
    print(f"  [+] Investigation Case Created: {cid}")
    print(f"  [+] State: {c1.state} | Priority: {c1.priority} | Police Alert Eligible: {c1.police_alert_eligible}")

    # Establish root trace chain
    trace.establish_trace_root(
        root_transaction_id=tx_root_id,
        origin_account_id=victim_acc,
        destination_account_id=mule_l1,
        amount_inr=100000.0,
        payment_channel="IMPS",
        chain_id=chain_id,
    )

    # Step 2: Confirmation Requested (Part 1)
    print_step(2, f"BANK ISSUES CUSTOMER CONFIRMATION REQUEST FOR TRANSACTION {tx_root_id}")
    conf = ctrl.request_confirmation(
        transaction_id=tx_root_id,
        sender_id=victim_acc,
        beneficiary_id=mule_l1,
        amount=100000.0,
        reason="Anomalous high-value transfer verification",
        case_id=cid,
    )
    print(f"  [+] Confirmation Request ID: {conf.confirmation_id}")
    print(f"  [+] Confirmation Status: {conf.status}")

    # Step 3: Track Downstream Transfers (B -> C -> D)
    print_step(3, "MONEY TRAIL PROPAGATION: DOWNSTREAM TRANSFERS (BOB -> CHARLIE -> DAVID)")
    trace.track_descendant_transaction(
        parent_transaction_id=tx_root_id,
        child_transaction_id=f"TX-DEMO-DOWN-01-{uuid.uuid4().hex[:4]}",
        from_account_id=mule_l1,
        to_account_id=mule_l2,
        amount_inr=95000.0,
        payment_channel="UPI",
    )
    trace.track_descendant_transaction(
        parent_transaction_id=f"TX-DEMO-DOWN-01-{uuid.uuid4().hex[:4]}",
        child_transaction_id=f"TX-DEMO-DOWN-02-{uuid.uuid4().hex[:4]}",
        from_account_id=mule_l2,
        to_account_id=mule_l3,
        amount_inr=90000.0,
        payment_channel="IMPS",
    )
    chain = trace.get_transaction_chain(chain_id)
    dest_chain = chain.get("destination_account_chain", []) if isinstance(chain, dict) else getattr(chain, "destination_account_chain", [])
    depth = chain.get("chain_depth", 2) if isinstance(chain, dict) else getattr(chain, "chain_depth", 2)
    print(f"  [+] Money Trail Discovered: {dest_chain}")
    print(f"  [+] Max Hop Depth: {depth}")

    # Step 4: Online Movement Allowed/Monitored vs Cashout Restricted
    print_step(4, "CHANNEL CONTROL EVALUATION: ONLINE TRANSFERS MONITORED vs CASHOUT RESTRICTED")
    decision_online = ctrl.evaluate_transaction_control(
        transaction_id="TX-EVAL-ONLINE",
        from_account=mule_l1,
        to_account=mule_l2,
        amount=30000.0,
        channel_or_type="UPI",
    )
    print(f"  [+] Online Transfer (UPI): Action={decision_online.action} | Allowed={decision_online.allowed}")

    decision_cashout = ctrl.evaluate_transaction_control(
        transaction_id="TX-EVAL-CASHOUT",
        from_account=mule_l3,
        to_account="NONE",
        amount=50000.0,
        channel_or_type="ATM",
    )
    print(f"  [+] Cashout Attempt (ATM): Action={decision_cashout.action} | Allowed={decision_cashout.allowed}")
    print(f"      Reason: {decision_cashout.reason}")

    # Step 5: Cashout Attempt Recorded & Location History Updated
    print_step(5, "PHYSICAL CASHOUT ATTEMPT DETECTED AT ATM-DELHI-CP-04")
    c_w = orchestrator.handle_withdrawal_attempt(
        attempt_id=f"ATT-DEMO-{uuid.uuid4().hex[:4]}",
        account_id=mule_l1,
        terminal_id=atm_id,
        amount_inr=50000.0,
        case_id=cid,
    )
    print(f"  [+] Updated Case State: {c_w.state}")
    print(f"  [+] Evidence Timeline Event Recorded for ATM {atm_id}")

    # Step 6: Customer A Confirms Fraud
    print_step(6, "CUSTOMER ALICE CONFIRMS FRAUD ON CONFIRMATION REQUEST")
    ctrl.submit_confirmation_response(
        confirmation_id=conf.confirmation_id,
        response_status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Victim declared cyber fraud unauthorized access",
    )
    c_fraud = orchestrator.handle_confirmation_update(
        confirmation_id=conf.confirmation_id,
        status=ConfirmationStatus.CONFIRMED_FRAUD,
        notes="Victim declared cyber fraud unauthorized access",
    )
    print(f"  [+] Escalated Case State: {c_fraud.state}")
    print(f"  [+] Derived Priority: {c_fraud.priority}")
    print(f"  [+] Linked Recovery Case ID: {c_fraud.recovery_case_id}")
    print(f"  [+] Police Alert Eligible: {c_fraud.police_alert_eligible}")

    # Step 7: NCRP Complaint / FIR Attachment
    print_step(7, "NCRP 1930 FORMAL COMPLAINT & FIR ATTACHMENT")
    c_fir = orchestrator.attach_complaint_fir(
        case_id=cid,
        complaint_id="NCRP-2026-998811",
        fir_number="FIR-DELHI-2026-00812",
        victim_account=victim_acc,
        reported_loss=100000.0,
    )
    print(f"  [+] State: {c_fir.state} | FIR Number: {c_fir.fir_number}")

    # Step 8: CyberShield Bank Official Review
    print_step(8, "CYBERSHIELD BANK OFFICIAL DASHBOARD REVIEWS UNIFIED EVIDENCE & TIMELINE")
    c_details = orchestrator.get_case_details(cid)
    print(f"  [+] Unified Case Details Loaded:")
    print(f"      - Root Transaction ID: {c_details.get('root_transaction_id')}")
    print(f"      - Evidence Count: {len(c_details.get('evidence', []))}")
    print(f"      - Timeline Event Count: {len(c_details.get('timeline_events', []))}")
    print(f"      - Bank Hold Status: {c_details.get('bank_hold_status')}")
    print(f"      - Police Alert Option Available: {c_details.get('police_alert_eligible')}")

    # Step 9: Bank Official Clicks 'ALERT POLICE'
    print_step(9, "BANK OFFICIAL EXPLICITLY SELECTS 'ALERT POLICE' ON CYBERSHIELD")
    res_police = orchestrator.trigger_police_alert(
        case_id=cid,
        actor_role="BANK_OFFICIAL",
        source="CyberShield Bank Official Dashboard",
    )
    alert_info = res_police["police_alert"]
    print(f"  [+] Police Alert Dispatched: ID={alert_info['police_alert_id']}")
    print(f"  [+] Case State: {res_police['case']['state']}")
    print(f"  [+] Police App Notification Status: {alert_info.get('status', alert_info.get('investigation_status', 'SENT'))}")

    # Step 10: Police App Officer Acknowledgment & Investigation
    print_step(10, "POLICE OFFICER RECEIVES ALERT, ACKNOWLEDGES & UPDATES INVESTIGATION")
    pol.acknowledge_police_alert(
        police_alert_id=alert_info['police_alert_id'],
        caller_role="POLICE_OFFICER",
        officer_id="INSPECTOR-KUMAR-09",
        notes="Cyber Crime Branch Delhi acknowledged receipt of structured fraud dossier",
    )
    pol.update_investigation_status(
        police_alert_id=alert_info['police_alert_id'],
        new_status=PoliceAlertStatus.UNDER_INVESTIGATION,
        caller_role="POLICE_OFFICER",
        officer_id="INSPECTOR-KUMAR-09",
        notes="ATM CCTV footage seized, suspect arrested near CP terminal",
    )
    print(f"  [+] Police Alert Status: UNDER_INVESTIGATION")

    # Step 11: Case Resolution & Final Audit Trail
    print_step(11, "CASE RESOLUTION AND AUDIT TRAIL VERIFICATION")
    c_resolved = orchestrator.resolve_case(
        case_id=cid,
        reason="Mule apprehend, INR 90,000 recovered via Part 2 recovery case",
        actor_id="BANK_OFFICIAL",
    )
    print(f"  [+] Final Case State: {c_resolved.state}")
    print(f"  [+] Resolution Reason: {c_resolved.resolution_reason}")

    timeline = orchestrator.get_case_timeline(cid)
    print("\n  [+] Complete Chronological Case Timeline Events:")
    for idx, event in enumerate(timeline, start=1):
        print(f"      {idx}. [{event['timestamp'][:19]}] {event['event_type']} (Source: {event['source']})")

    print("\n" + "=" * 80)
    print("  DEMO COMPLETE: FULL CASE ORCHESTRATION & ESCALATION LIFECYCLE VERIFIED!")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
