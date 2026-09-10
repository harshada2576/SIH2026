"""scripts/demo_police_alert_workflow.py — End-to-End Part 5 Demo Scenario Script.

Demonstrates complete Bank Official to Police LEA Alert & Status Sync Workflow:
1. Fraud pattern detected & case initialized in SQLite/CyberShield.
2. Provenance money trail traced & withdrawal attempt recorded at ATM.
3. Bank official reviews case in CyberShield and clicks "ALERT POLICE".
4. PoliceAlertManager generates data-minimized PoliceAlertRecord.
5. Police Alert App receives alert in LEA queue (GET /police-alerts).
6. Police officer views complete incident details, origin tx, money trail, ATM evidence, nearby terminals & timeline.
7. Police officer acknowledges receipt (SENT -> ACKNOWLEDGED).
8. Police officer updates investigation status (ACKNOWLEDGED -> UNDER_INVESTIGATION).
9. CyberShield reads updated status live.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from pipeline.police_alert_delivery import PoliceAlertManager
from shared.persistence import Store
from shared.schemas import CaseRecord, PoliceAlertStatus, PredictedTerminal, TransactionEvent


def run_demo():
    print("=" * 80)
    print("  SIH26184 — PART 5 DEMO: POLICE ALERT APP & ALERT DELIVERY WORKFLOW")
    print("=" * 80)

    # Initialize persistence & engines
    db_path = Path(__file__).resolve().parent.parent / "data" / "output" / "cybershield.db"
    store = Store(db_path=db_path)
    trace = FundTraceabilityEngine(store=store)
    geo = WithdrawalGeoIntelligence(store=store)
    police_mgr = PoliceAlertManager(store=store, trace_engine=trace, geo_intel=geo)

    case_id = f"CASE-DEMO-POLICE-{int(time.time())}"
    root_tx_id = f"TXN-ROOT-POL-{int(time.time())}"
    mule_acc = "ACC-MULE-7777"
    agg_acc = "ACC-AGGREGATOR-9999"

    print(f"\n[STEP 1] Fraud Pattern Detected -> Initializing Case: {case_id}")

    # Seed root transaction
    tx = TransactionEvent(
        transaction_id=root_tx_id,
        source_account_id="ACC-VICTIM-8888",
        target_account_id=mule_acc,
        amount_inr=250000.0,
        timestamp=datetime.now(timezone.utc).isoformat(),
        payment_channel="IMPS",
        device_fingerprint="DEV-FINGERPRINT-POL-01",
    )
    store.save_transaction(tx)

    # Establish provenance chain (Part 2)
    trace.establish_trace_root(
        root_transaction_id=root_tx_id,
        origin_account_id="ACC-VICTIM-8888",
        destination_account_id=mule_acc,
        amount_inr=250000.0,
    )
    trace.track_descendant_transaction(
        parent_transaction_id=root_tx_id,
        child_transaction_id=f"TXN-HOP2-{int(time.time())}",
        from_account_id=mule_acc,
        to_account_id=agg_acc,
        amount_inr=240000.0,
        payment_channel="UPI",
    )

    # Save initial CaseRecord (Part 4 / CyberShield)
    case_record = CaseRecord(
        case_id=case_id,
        flagged_account_id=mule_acc,
        state="PRE_COMPLAINT_INTERVENTION",
        risk_score=0.95,
        confidence=0.91,
        band="CRITICAL",
        suspicious_amount=250000.0,
        protected_amount=240000.0,
        existing_balance=35000.0,
        money_trail=[
            {
                "hop_index": 1,
                "source_account_id": "ACC-VICTIM-8888",
                "target_account_id": mule_acc,
                "amount_inr": 250000.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payment_channel": "IMPS",
                "suspicious_flags": ["SUSPICIOUS_HIGH_VALUE"],
            },
            {
                "hop_index": 2,
                "source_account_id": mule_acc,
                "target_account_id": agg_acc,
                "amount_inr": 240000.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payment_channel": "UPI",
                "suspicious_flags": ["RAPID_FORWARDING"],
            },
        ],
        predicted_terminals=[
            PredictedTerminal(
                terminal_id="ATM-SBI-ND-042",
                probability=0.92,
                latitude=28.5708,
                longitude=77.3261,
            )
        ],
        evidence=[
            "Rapid forwarding through multiple mule accounts within 4 minutes",
            "Shared device fingerprint across 5 unlinked victim transfers",
            "High confidence predicted cash-out terminal targeting ATM-SBI-ND-042",
        ],
        lea_notification_status="NONE",
    )
    store.save_case(case_record)
    print(f"  [+] Case {case_id} persisted in SQLite. Band: CRITICAL (Risk: 95%).")

    # Record withdrawal attempt at predicted ATM (Part 3)
    print(f"\n[STEP 2] Cashout Withdrawal Attempt Detected at Physical ATM")
    attempt = geo.process_withdrawal_attempt(
        attempt_id=f"ATT-POL-{int(time.time())}",
        account_id=agg_acc,
        terminal_id="ATM-SBI-ND-042",
        amount_inr=20000.0,
        case_id=case_id,
    )
    print(f"  [+] Withdrawal attempt at {attempt.terminal_id}: Status = {attempt.status} ({attempt.reason})")

    # Bank Official Action -> Clicks ALERT POLICE
    print(f"\n[STEP 3] Bank Official Reviews Case in CyberShield & Selects 'ALERT POLICE'")
    alert_record = police_mgr.create_police_alert(
        case_id=case_id,
        caller_role="BANK_OFFICIAL",
        source="CyberShield Bank Official Dashboard",
    )
    print(f"  [+] Police Alert Package Created: {alert_record.police_alert_id}")
    print(f"  [+] Alert Status: {alert_record.alert_status} | Priority: {alert_record.priority}")

    # Police Alert App Receives Case
    print(f"\n[STEP 4] Police Alert App Receives Alert in LEA Queue")
    police_queue = police_mgr.list_police_alerts(limit=5)
    received = next((a for a in police_queue if a["police_alert_id"] == alert_record.police_alert_id), None)
    assert received is not None
    print(f"  [+] Received Alert in Police Queue: {received['police_alert_id']} (Case: {received['case_id']})")
    print(f"  [+] Money Trail Hops: {len(received['money_trail'])} hops | Withdrawal Attempts: {len(received['withdrawal_attempts'])}")
    print(f"  [+] Nearby Terminals Discovered: {len(received['nearby_terminals'])} alternative ATMs nearby")

    # Police Officer Opens Alert & Acknowledges Receipt
    print(f"\n[STEP 5] Police Officer Opens Alert Package & Clicks 'ACKNOWLEDGE'")
    ack_result = police_mgr.acknowledge_police_alert(
        police_alert_id=alert_record.police_alert_id,
        caller_role="POLICE_OFFICER",
        officer_id="INSPECTOR-RAHUL-VERMA",
        notes="Acknowledged receipt. Field patrol dispatched to ATM-SBI-ND-042.",
    )
    print(f"  [+] Police Alert Status Updated: {ack_result.alert_status}")
    print(f"  [+] Acknowledged By: {ack_result.acknowledged_by} at {ack_result.acknowledged_at}")

    # Verify CyberShield sees updated status live
    synced_case = store.get_case(case_id)
    print(f"  [+] CyberShield Live Case Status Sync: LEA Notification Status = {synced_case['lea_notification_status']}")

    # Police Officer Updates Investigation Status -> UNDER_INVESTIGATION
    print(f"\n[STEP 6] Police Officer Updates Investigation Status -> UNDER_INVESTIGATION")
    inv_result = police_mgr.update_investigation_status(
        police_alert_id=alert_record.police_alert_id,
        new_status=PoliceAlertStatus.UNDER_INVESTIGATION,
        caller_role="POLICE_OFFICER",
        officer_id="INSPECTOR-RAHUL-VERMA",
        notes="Suspect intercepted at ATM kiosk. Interrogation underway.",
    )
    print(f"  [+] Police Alert Status Updated: {inv_result.alert_status}")

    # CyberShield bidirectional status check
    synced_case2 = store.get_case(case_id)
    print(f"  [+] CyberShield Live Case Status Sync: LEA Notification Status = {synced_case2['lea_notification_status']}")

    print("\n" + "=" * 80)
    print("  PART 5 DEMO SUCCESSFUL: Complete Bank -> Police workflow verified end-to-end!")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
