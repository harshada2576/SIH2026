"""tests/test_operational_scenarios.py — Comprehensive test suite for SIH26184 Scenarios A-E.

Tests:
1. Scenario A: Pre-complaint predictive intervention (provisional hold, predicted ATM, LEA notify, no complaint ID needed)
2. Scenario B: Post-complaint escalation (transition from predictive to complaint-backed hard freeze + physical ATM block + LEA dispatch)
3. Scenario C: Actual withdrawal attempt correlation (correlates terminal, case, records attempt, calculates proximity)
4. Scenario D: Repeated ATM targeting (Account X -> ATM repeated activity escalates risk level)
5. Scenario E: Selective funds protection (distinguishes existing balance vs recent suspicious funds)
6. Persistence & Idempotency: SQLite persistence for cases, selective holds, blocks, attempts, and duplicate handling.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from detection import auto_intervention, scorer
from pipeline.graph_store import GraphStore
from shared.persistence import Store
from shared.schemas import (
    AccountNodeMetadata,
    CaseLifecycleState,
    CaseRecord,
    MoneyTrailLeg,
    PredictedTerminal,
    RiskAlert,
    SelectiveFundProtection,
    TerminalBlockRequest,
    TerminalNode,
    TransactionEvent,
    WithdrawalAttemptEvent,
)


@pytest.fixture
def temp_store(tmp_path):
    db_path = tmp_path / "test_cybershield.db"
    store = Store(db_path=db_path)
    yield store
    store.close()


@pytest.fixture
def populated_graph():
    graph = GraphStore()
    now = datetime.now(timezone.utc)

    # 1. Terminals
    terminals = [
        TerminalNode(terminal_id="ATM-SBI-ND-042", terminal_type="ATM_KIOSK", latitude=28.5708, longitude=77.3261, district_pincode="201301"),
        TerminalNode(terminal_id="AEPS-PM-ND-118", terminal_type="AEPS_MICRO_ATM", latitude=28.5722, longitude=77.3248, district_pincode="201301"),
        TerminalNode(terminal_id="ATM-HDFC-ND-087", terminal_type="ATM_KIOSK", latitude=28.5695, longitude=77.3275, district_pincode="201301"),
    ]
    graph.load_terminals([t.to_dict() for t in terminals])

    # 2. Account nodes
    victim = "ACC-VICTIM100"
    mule_a = "ACC-MULEA01"
    mule_b = "ACC-MULEB02"
    aggregator = "ACC-AGGREGATOR03"

    graph.add_account_metadata(AccountNodeMetadata(account_id=victim, account_tier="victim", account_age_days=600))
    graph.add_account_metadata(AccountNodeMetadata(account_id=mule_a, account_tier="mule_l1", account_age_days=10, historical_terminal_ids=["ATM-SBI-ND-042"]))
    graph.add_account_metadata(AccountNodeMetadata(account_id=mule_b, account_tier="mule_l2", account_age_days=8, historical_terminal_ids=["ATM-SBI-ND-042"]))
    graph.add_account_metadata(AccountNodeMetadata(account_id=aggregator, account_tier="aggregator", account_age_days=3, historical_terminal_ids=["ATM-SBI-ND-042", "AEPS-PM-ND-118"]))

    # 3. Layered Transactions: Victim (100k) -> Mule A (96k) -> Mule B (92k) -> Aggregator
    t0 = now - timedelta(minutes=15)
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-SCENARIO-01",
        source_account_id=victim,
        target_account_id=mule_a,
        amount_inr=100000.0,
        timestamp=t0,
        payment_channel="IMPS",
        device_fingerprint="DEV-VICTIM-APP",
    ))
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-SCENARIO-02",
        source_account_id=mule_a,
        target_account_id=mule_b,
        amount_inr=96000.0,
        timestamp=t0 + timedelta(minutes=2),
        payment_channel="UPI",
        device_fingerprint="DEV-MULE-SHARED",
    ))
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-SCENARIO-03",
        source_account_id=mule_b,
        target_account_id=aggregator,
        amount_inr=92000.0,
        timestamp=t0 + timedelta(minutes=4),
        payment_channel="UPI",
        device_fingerprint="DEV-MULE-SHARED",
    ))

    return graph


def test_scenario_a_pre_complaint_prevention(populated_graph, temp_store):
    """Scenario A: High risk + confidence triggers PRE-COMPLAINT provisional intervention without a complaint ID."""
    aggregator = "ACC-AGGREGATOR03"
    case = scorer.build_investigation_case(populated_graph, aggregator, complaint_id=None)

    assert case.state == CaseLifecycleState.PRE_COMPLAINT_INTERVENTION
    assert case.complaint_id is None
    assert case.flagged_account_id == aggregator
    assert case.suspicious_amount >= 92000.0
    assert len(case.money_trail) >= 2
    assert len(case.predicted_terminals) > 0
    assert case.predicted_terminals[0].terminal_id == "ATM-SBI-ND-042"

    # Auto-intervention decision
    alert = RiskAlert(
        complaint_id=case.case_id,
        risk_score=case.risk_score,
        flagged_account_id=aggregator,
        predicted_terminals=case.predicted_terminals,
        evidence=case.evidence,
        confidence=case.confidence,
    )
    decision = auto_intervention.decide(alert, band="CRITICAL", pre_complaint=True, funds_breakdown={
        "suspicious_amount": case.suspicious_amount,
        "existing_balance": case.existing_balance,
        "protected_amount": case.protected_amount,
    })

    assert decision.pre_complaint is True
    assert decision.selective_hold_details is not None
    assert decision.selective_hold_details["protected_amount"] == case.protected_amount
    assert decision.terminal_block_requested is True

    # Persist case & verify in SQLite
    case.terminal_block_status = "REQUESTED"
    temp_store.save_case(case)
    retrieved = temp_store.get_case(case.case_id)
    assert retrieved is not None
    assert retrieved["state"] == CaseLifecycleState.PRE_COMPLAINT_INTERVENTION
    assert retrieved["flagged_account_id"] == aggregator


def test_scenario_b_post_complaint_escalation(populated_graph, temp_store):
    """Scenario B: Transition from predictive pre-complaint case to complaint-backed physical escalation."""
    aggregator = "ACC-AGGREGATOR03"
    pre_case = scorer.build_investigation_case(populated_graph, aggregator, complaint_id=None)
    assert pre_case.state == CaseLifecycleState.PRE_COMPLAINT_INTERVENTION

    temp_store.save_case(pre_case)

    # Formal victim complaint arrives
    formal_complaint_id = "CMP-2026-994821"
    post_case = scorer.build_investigation_case(populated_graph, aggregator, complaint_id=formal_complaint_id)

    assert post_case.state == CaseLifecycleState.POST_COMPLAINT_ESCALATED
    assert post_case.complaint_id == formal_complaint_id

    alert = RiskAlert(
        complaint_id=formal_complaint_id,
        risk_score=post_case.risk_score,
        flagged_account_id=aggregator,
        predicted_terminals=post_case.predicted_terminals,
        evidence=post_case.evidence,
        confidence=post_case.confidence,
    )
    decision = auto_intervention.decide(alert, band=post_case.band, pre_complaint=False)

    assert decision.tier == "POST_COMPLAINT_ESCALATED"
    assert decision.bank_action == "freeze"
    assert decision.terminal_block_requested is True
    assert decision.lea_notified is True

    temp_store.save_case(post_case)
    saved = temp_store.get_case(post_case.case_id)
    assert saved["state"] == CaseLifecycleState.POST_COMPLAINT_ESCALATED
    assert saved["complaint_id"] == formal_complaint_id


def test_scenario_c_actual_withdrawal_attempt_correlation(populated_graph, temp_store):
    """Scenario C: Cashout attempt at predicted terminal ATM-SBI-ND-042 correlates with active case."""
    aggregator = "ACC-AGGREGATOR03"
    case = scorer.build_investigation_case(populated_graph, aggregator)
    case.terminal_block_status = "REQUESTED"
    temp_store.save_case(case)

    # Cashout attempt event
    attempt = WithdrawalAttemptEvent(
        attempt_id="ATT-DEMO-001",
        terminal_id="ATM-SBI-ND-042",
        account_id=aggregator,
        amount_inr=90000.0,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    matched_case, summary = scorer.correlate_withdrawal_attempt(populated_graph, attempt, active_cases=[case])

    assert matched_case is not None
    assert summary["correlated"] is True
    assert summary["terminal_matched"] is True
    assert summary["distance_to_predicted_km"] == 0.0
    assert summary["action_taken"] == "BLOCKED"
    assert attempt.is_blocked is True
    assert matched_case.state == CaseLifecycleState.CASHOUT_ATTEMPT_DETECTED
    nearby_cnt = len(summary["nearby_terminals_count"]) if isinstance(summary.get("nearby_terminals_count"), list) else summary["nearby_terminals_count"]
    assert nearby_cnt > 0

    # Save attempt & updated case to store
    temp_store.save_withdrawal_attempt(attempt)
    temp_store.save_case(matched_case)

    attempts_in_db = temp_store.get_withdrawal_attempts(terminal_id="ATM-SBI-ND-042")
    assert len(attempts_in_db) == 1
    assert attempts_in_db[0]["is_blocked"] == 1
    assert attempts_in_db[0]["correlated_case_id"] == matched_case.case_id


def test_scenario_d_repeated_atm_targeting_escalation(populated_graph, temp_store):
    """Scenario D: Repeated ATM usage by same account escalates risk from MONITORED to PERSISTENT_TERMINAL_RISK."""
    account_id = "ACC-REPEAT-MULE"
    terminal_id = "ATM-SBI-ND-042"
    now = datetime.now(timezone.utc)

    # 1st attempt -> Initial Monitor
    rec1 = scorer.evaluate_repeated_targeting(populated_graph, account_id, terminal_id, timestamp=now - timedelta(hours=2))
    assert rec1["occurrence_count"] == 1
    assert rec1["escalation_state"] == "MONITORED"
    count1 = temp_store.record_terminal_activity(account_id, terminal_id, (now - timedelta(hours=2)).isoformat())
    assert count1 == 1

    # 2nd attempt -> Elevated Risk
    rec2 = scorer.evaluate_repeated_targeting(populated_graph, account_id, terminal_id, timestamp=now - timedelta(hours=1))
    assert rec2["occurrence_count"] == 2
    assert rec2["escalation_state"] == "ELEVATED_RISK"
    count2 = temp_store.record_terminal_activity(account_id, terminal_id, (now - timedelta(hours=1)).isoformat())
    assert count2 == 2

    # 3rd attempt -> Persistent Terminal Risk & Escalated Block
    rec3 = scorer.evaluate_repeated_targeting(populated_graph, account_id, terminal_id, timestamp=now)
    assert rec3["occurrence_count"] == 3
    assert rec3["escalation_state"] == "PERSISTENT_TERMINAL_RISK"
    assert rec3["risk_multiplier"] == 1.5
    count3 = temp_store.record_terminal_activity(account_id, terminal_id, now.isoformat())
    assert count3 == 3


def test_scenario_e_selective_funds_protection(populated_graph, temp_store):
    """Scenario E: Selective protection holds recently received suspicious amount while preserving existing balance."""
    mule = "ACC-SELECTIVE-MULE"
    now = datetime.now(timezone.utc)

    # Older legitimate transactions (2 hours ago) -> net existing balance ₹20,000
    populated_graph.add_account_metadata(AccountNodeMetadata(account_id=mule, account_tier="mule_l1", account_age_days=100))
    populated_graph.add_transaction(TransactionEvent(
        transaction_id="TXN-LEGIT-OLD-01",
        source_account_id="ACC-SALARY-EMPLOYER",
        target_account_id=mule,
        amount_inr=50000.0,
        timestamp=now - timedelta(hours=5),
        payment_channel="NEFT",
        device_fingerprint="DEV-MULE-HOME",
    ))
    populated_graph.add_transaction(TransactionEvent(
        transaction_id="TXN-LEGIT-OLD-02",
        source_account_id=mule,
        target_account_id="ACC-GROCERY-STORE",
        amount_inr=30000.0,
        timestamp=now - timedelta(hours=4),
        payment_channel="UPI",
        device_fingerprint="DEV-MULE-HOME",
    ))

    # Recent fraud transaction (10 minutes ago) -> ₹80,000 suspicious funds
    populated_graph.add_transaction(TransactionEvent(
        transaction_id="TXN-FRAUD-RECENT-01",
        source_account_id="ACC-VICTIM100",
        target_account_id=mule,
        amount_inr=80000.0,
        timestamp=now - timedelta(minutes=10),
        payment_channel="IMPS",
        device_fingerprint="DEV-MULE-FRAUD",
    ))

    funds = populated_graph.compute_account_funds(mule, window_seconds=3600, as_of=now)

    assert funds["existing_balance"] == 20000.0
    assert funds["suspicious_amount"] == 80000.0
    assert funds["protected_amount"] == 80000.0

    # Create selective hold record
    hold = SelectiveFundProtection(
        account_id=mule,
        existing_balance=funds["existing_balance"],
        suspicious_amount=funds["suspicious_amount"],
        protected_amount=funds["protected_amount"],
        source_transaction_id="TXN-FRAUD-RECENT-01",
        chain_reference="CHAIN-ACC-VICTIM100",
        reason="Selective Provisional Hold on Recent Cyber Fraud Ingress",
        intervention_type="PROVISIONAL_HOLD",
        status="ACTIVE",
    )

    temp_store.save_selective_hold(hold)
    holds_in_db = temp_store.get_selective_holds(account_id=mule)

    assert len(holds_in_db) == 1
    assert holds_in_db[0]["existing_balance"] == 20000.0
    assert holds_in_db[0]["protected_amount"] == 80000.0
    assert holds_in_db[0]["status"] == "ACTIVE"


def test_money_trail_reconstruction_details(populated_graph):
    """Verifies detailed chronological money trail extraction."""
    aggregator = "ACC-AGGREGATOR03"
    trail = populated_graph.reconstruct_detailed_chain(aggregator)

    assert len(trail) >= 2
    # First hop must be from victim
    assert trail[0].hop_index == 1
    assert trail[0].source_account_id == "ACC-VICTIM100"
    assert trail[0].source_tier == "victim"
    # Amounts should match the chain
    assert trail[0].amount_inr == 100000.0
    assert trail[1].hop_index == 2
    assert trail[1].amount_inr == 96000.0


def test_nearby_terminals_calculation(populated_graph):
    """Verifies spatial intelligence and Haversine distance calculations."""
    nearby = populated_graph.find_nearby_terminals("ATM-SBI-ND-042", radius_km=5.0)
    assert len(nearby) >= 2
    # Distances must be non-negative and sorted ascending
    for n in nearby:
        assert n["distance_km"] >= 0.0
    assert nearby[0]["distance_km"] <= nearby[-1]["distance_km"]
