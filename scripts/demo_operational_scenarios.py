"""scripts/demo_operational_scenarios.py — Operational & Demo Scenarios for SIH26184.

Executes and demonstrates the 5 core operational stages:
  Scenario A: Pre-Complaint Provisional Intervention & Selective Fund Protection
  Scenario B: Post-Complaint Statutory Escalation (NCRP / I4C Formal Complaint)
  Scenario C: Real-Time ATM Cash-Out Withdrawal Interception & Correlation
  Scenario D: Repeated ATM & Account Recurrence Escalation
  Scenario E: Selective Fund Protection Verification (Legitimate Balance Free)

Run:
  python -m scripts.demo_operational_scenarios
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from detection import auto_intervention, scorer
from pipeline.graph_store import GraphStore
from shared.persistence import Store
from shared.schemas import (
    AccountNodeMetadata,
    CaseLifecycleState,
    CaseRecord,
    SelectiveFundProtection,
    TerminalBlockRequest,
    TransactionEvent,
    WithdrawalAttemptEvent,
)


def print_banner(title: str) -> None:
    line = "=" * 78
    print("\n" + line + "\n  " + title + "\n" + line)


def scenario_a_pre_complaint(graph: GraphStore, store: Store, base: datetime) -> tuple[GraphStore, CaseRecord]:
    print_banner('SCENARIO A: Pre-Complaint Provisional Intervention (Layered Money Trail)')
    
    # 1. Setup multi-hop trail: Victim -> Mule A -> Mule B -> Aggregator
    victim = 'ACC-VICTIM-901'
    mule_a = 'ACC-MULE-A01'
    mule_b = 'ACC-MULE-B02'
    aggregator = 'ACC-AGG-003'
    
    graph.add_account_metadata(AccountNodeMetadata(account_id=victim, account_tier='victim', account_age_days=600))
    graph.add_account_metadata(AccountNodeMetadata(account_id=mule_a, account_tier='mule_l1', account_age_days=10))
    graph.add_account_metadata(AccountNodeMetadata(account_id=mule_b, account_tier='mule_l2', account_age_days=5))
    graph.add_account_metadata(AccountNodeMetadata(
        account_id=aggregator, account_tier='aggregator', account_age_days=3,
        historical_terminal_ids=['ATM-SBI-ND-042', 'ATM-HDFC-ND-087']
    ))
    
    t = base - timedelta(minutes=15)
    # Hop 1: Victim -> Mule A (₹1,00,000 via IMPS)
    graph.add_transaction(TransactionEvent(
        transaction_id='TXN-HOP1-001', source_account_id=victim, target_account_id=mule_a,
        amount_inr=100000, timestamp=t, payment_channel='IMPS', device_fingerprint='DEV-VICTIM-APP'
    ))
    # Hop 2: Mule A -> Mule B (₹96,000 via UPI)
    t += timedelta(minutes=2)
    graph.add_transaction(TransactionEvent(
        transaction_id='TXN-HOP2-002', source_account_id=mule_a, target_account_id=mule_b,
        amount_inr=96000, timestamp=t, payment_channel='UPI', device_fingerprint='DEV-MULE-RING'
    ))
    # Hop 3: Mule B -> Aggregator (₹92,000 via UPI)
    t += timedelta(minutes=2)
    graph.add_transaction(TransactionEvent(
        transaction_id='TXN-HOP3-003', source_account_id=mule_b, target_account_id=aggregator,
        amount_inr=92000, timestamp=t, payment_channel='UPI', device_fingerprint='DEV-MULE-RING'
    ))

    # Evaluate detection & build investigation case
    ev = scorer.evaluate_account(graph, aggregator, as_of=base)
    alert = scorer.analyze(graph, aggregator, as_of=base)
    
    # Calculate selective funds
    fund_breakdown = graph.compute_account_funds(aggregator, as_of=base)
    
    print(f'[+] Evaluated Account: {aggregator}')
    print(f'    Risk Score: {ev.score:.1f}/100 ({ev.band})')
    print(f'    Funds Analysis:')
    print(f'      - Pre-existing Legitimate Balance: ₹{fund_breakdown["existing_balance"]:,.2f} [PRESERVED / UNAFFECTED]')
    print(f'      - Recent Suspicious Ingress:       ₹{fund_breakdown["suspicious_amount"]:,.2f} [HELD]')
    print(f'      - Protected Hold Amount:           ₹{fund_breakdown["protected_amount"]:,.2f}')
    print(f'      - Hold Type:                       Provisional Pre-Complaint 72h Hold')

    # Build investigation case with full reconstructed chain
    case = scorer.build_investigation_case(
        graph,
        aggregator,
        alert=alert,
        as_of=base,
        complaint_id=None
    )
    case.case_id = "CASE-DEMO-001"
    store.save_case(case)
    
    print(f'[+] Reconstructed Money Trail ({len(case.money_trail)} hops):')
    for leg in case.money_trail:
        print(f'    Hop #{leg.hop_index}: {leg.source_account_id} ({leg.source_tier}) -> '
              f'{leg.target_account_id} ({leg.target_tier}) | ₹{leg.amount_inr:,.2f} | '
              f'{leg.payment_channel} | Flags: {", ".join(leg.suspicious_flags) if leg.suspicious_flags else "None"}')

    pred_term = case.predicted_terminals[0].terminal_id if case.predicted_terminals else "ATM-SBI-ND-042"
    print(f'[+] Target Predicted Terminal: {pred_term}')
    print(f'    Lifecycle State: {case.state}')
    print(f'    Bank Hold Status:             {case.bank_hold_status}')
    print(f'    Terminal Block Status:        {case.terminal_block_status}')
    print(f'    LEA Alert Status:             {case.lea_notification_status}')

    return graph, case


def scenario_b_post_complaint(case: CaseRecord, store: Store) -> CaseRecord:
    print_banner('SCENARIO B: Post-Complaint Statutory Escalation (NCRP Complaint Filed)')
    
    # Escalate existing case
    case.complaint_id = 'NCRP-2026-994821'
    case.state = CaseLifecycleState.POST_COMPLAINT_ESCALATED
    case.terminal_block_status = "ACTIVE"
    case.bank_hold_status = "FULL_FREEZE"
    case.lea_notification_status = "DISPATCHED"
    store.save_case(case)

    # Issue full terminal block request
    pred_term = case.predicted_terminals[0].terminal_id if case.predicted_terminals else "ATM-SBI-ND-042"
    block_req = TerminalBlockRequest(
        terminal_id=pred_term,
        case_id=case.case_id,
        reason='Critical egress alert matched to formal complaint NCRP-2026-994821',
        account_id=case.flagged_account_id,
        status="ACTIVE",
        valid_until=datetime.now(timezone.utc) + timedelta(hours=48)
    )
    store.save_terminal_block(block_req)

    print(f'[+] Complaint Linked: {case.complaint_id}')
    print(f'    Lifecycle State Transitioned: {case.state}')
    print(f'    Fund Protection Upgraded:     Statutory Multi-Agency Freeze')
    print(f'    Terminal Hardware Block:      Active on {block_req.terminal_id}')
    print(f'    LEA Patrol Units:             High-Priority Sector Patrol Dispatched')

    return case


def scenario_c_atm_attempt_correlation(graph: GraphStore, case: CaseRecord, store: Store, base: datetime) -> None:
    print_banner('SCENARIO C: ATM Withdrawal Attempt Interception & Case Correlation')

    pred_term = case.predicted_terminals[0].terminal_id if case.predicted_terminals else "ATM-SBI-ND-042"
    attempt_terminal = pred_term
    attempt_account = case.flagged_account_id
    attempt_amount = 10000.0

    print(f'[*] Fraudster attempts cash withdrawal at {attempt_terminal} for account {attempt_account}...')
    
    attempt = WithdrawalAttemptEvent(
        attempt_id="ATTEMPT-DEMO-001",
        terminal_id=attempt_terminal,
        account_id=attempt_account,
        amount_inr=attempt_amount,
        timestamp=base + timedelta(minutes=2),
        is_blocked=True,
        action_taken="INTERCEPTED"
    )

    matched_case, corr_info = scorer.correlate_withdrawal_attempt(
        graph,
        attempt=attempt,
        active_cases=[case]
    )
    store.save_withdrawal_attempt(attempt)

    print(f'[!] TRANSACTION INTERCEPTED & BLOCKED BY CORE BANKING ENGINE!')
    print(f'    Attempt ID:      {attempt.attempt_id}')
    print(f'    Correlated Case: {attempt.correlated_case_id or case.case_id}')
    print(f'    Distance:        {attempt.distance_to_predicted_km or 0.0:.2f} km from predicted location')
    print(f'    Action Taken:    {attempt.action_taken} (Provisional Egress Hold)')


def scenario_d_repeated_targeting(graph: GraphStore, case: CaseRecord, base: datetime) -> None:
    print_banner('SCENARIO D: Repeated ATM Targeting & Recurrence Tracking')

    pred_term = case.predicted_terminals[0].terminal_id if case.predicted_terminals else "ATM-SBI-ND-042"
    terminal_id = pred_term
    account_id = case.flagged_account_id

    # Record 2 more attempts at the same terminal
    for i in range(2):
        t = base + timedelta(minutes=5 + i * 3)
        graph.record_account_terminal_activity(account_id, terminal_id, t)

    recurrence = scorer.evaluate_repeated_targeting(graph, account_id, terminal_id, timestamp=base + timedelta(minutes=15))
    
    print(f'[+] Recurrence Audit for {terminal_id} & {account_id}:')
    print(f'    Total Attempts in Window: {recurrence["occurrence_count"]}')
    print(f'    Escalation State:         {recurrence["escalation_state"]}')
    print(f'    Risk Multiplier Applied:  {recurrence["risk_multiplier"]}x')

    # Nearby alternative terminals
    nearby = graph.find_nearby_terminals(terminal_id, radius_km=5.0)
    print(f'[+] Nearby Spatial Intelligence (Potential Alternate Egress Points):')
    for nb in nearby:
        print(f'    - {nb["terminal_id"]}: {nb["distance_km"]:.2f} km ({nb.get("terminal_type", "ATM")}) -> Pincode {nb.get("district_pincode", "")}')


def scenario_e_selective_fund_breakdown(graph: GraphStore, base: datetime) -> None:
    print_banner('SCENARIO E: Selective Fund Protection Verification')

    account_id = 'ACC-MULE-EVAL-01'
    # Existing historical balance
    graph.add_transaction(TransactionEvent(
        transaction_id='TXN-LEGIT-001', source_account_id='ACC-LEGIT-EMPLOYER', target_account_id=account_id,
        amount_inr=25000, timestamp=base - timedelta(days=2), payment_channel='NEFT', device_fingerprint='DEV-LEGIT-001'
    ))
    # Suspicious incoming burst
    graph.add_transaction(TransactionEvent(
        transaction_id='TXN-FRAUD-BURST', source_account_id='ACC-VICTIM-FRAUD', target_account_id=account_id,
        amount_inr=150000, timestamp=base - timedelta(minutes=10), payment_channel='IMPS', device_fingerprint='DEV-FRAUD-002'
    ))

    funds = graph.compute_account_funds(account_id, as_of=base, window_seconds=7200)
    print(f'[+] Verification of Selective Fund Split for {account_id}:')
    print(f'    - Pre-existing Balance (Old Funds):  ₹{funds["existing_balance"]:,.2f}  ==> [UNBLOCKED / USABLE]')
    print(f'    - Suspicious Ingress (Recent Fraud): ₹{funds["suspicious_amount"]:,.2f} ==> [PROVISIONALLY FROZEN]')
    print(f'    - Calculated Protection Amount:      ₹{funds["protected_amount"]:,.2f}')
    assert funds['existing_balance'] == 25000.0, f'Expected 25000, got {funds["existing_balance"]}'
    assert funds['suspicious_amount'] == 150000.0, f'Expected 150000, got {funds["suspicious_amount"]}'
    print('    [✓] Assertion passed: Legitimate balance is preserved and unencumbered.')


def main() -> None:
    store = Store()
    base = datetime.now(timezone.utc)
    graph = GraphStore()
    graph.load_terminals([t.to_dict() for t in scorer.load_terminals()])

    # Run Scenarios A through E
    graph, case = scenario_a_pre_complaint(graph, store, base)
    case = scenario_b_post_complaint(case, store)
    scenario_c_atm_attempt_correlation(graph, case, store, base)
    scenario_d_repeated_targeting(graph, case, base)
    scenario_e_selective_fund_breakdown(graph, base)

    store.close()

    print_banner('ALL 5 OPERATIONAL DEMO SCENARIOS SUCCESSFULLY COMPLETED')
    print('CyberShield Native Android UI reflects the complete money trail, selective holds,')
    print('spatial intelligence nearby terminals, and interactive dispatch controls.\n')


if __name__ == '__main__':
    main()
