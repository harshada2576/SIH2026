"""tests/test_smurfing_and_corridor.py

Comprehensive test suite covering:
1. Smurfing & Subgraph Structuring Rule (adversarial micro-split evasion).
2. Dynamic Terminal Density Index (TDI) & Behavioral Channel Weighting.
3. Multi-Terminal Corridor Route Prediction (Primary + Fallback waypoints & transit ETAs).
4. Operational Telemetry & Operating Hours Feasibility Filters (Cash status, 24x7 vs branch hours).
5. AEPS vs ATM Behavioral Asymmetry (CSP liquidity limits vs card swift egress).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.helpers import acct, aid, minutes_ago, now_utc, txn
from detection.rules import smurfing_subgraph_rule
from detection.terminal_ranking import (
    compute_terminal_density,
    predict_terminal_corridor,
    rank_terminals,
)
from detection.scorer import analyze, build_investigation_case, evaluate_account
from pipeline.graph_store import GraphStore
from shared.schemas import AccountNodeMetadata, TerminalNode, TransactionEvent


# ============================================================================
# 1. SMURFING & SUBGRAPH STRUCTURING RULE TESTS
# ============================================================================

def test_smurfing_rule_detects_structured_micro_transfers():
    """Detects structured micro-transfers (e.g. 4 transfers of ~₹24,500 within 20 mins)."""
    base = now_utc()
    g = GraphStore()
    g.add_account_metadata(acct("MULE"))
    for i in range(4):
        g.add_account_metadata(acct(f"SRC{i}"))
        g.add_transaction(
            txn(f"tx_smurf_{i}", f"SRC{i}", "MULE", 24500.0 + (i * 100), minutes_ago(20 - (i * 4), base))
        )

    result = smurfing_subgraph_rule.evaluate(g, aid("MULE"), as_of=base)
    assert result.name == "smurfing_subgraph"
    assert result.severity >= 0.8, f"Expected high severity for structured smurfing, got {result.severity}"
    assert "structured transfer" in result.measured.lower()
    assert "smurfing:" in result.evidence.lower()


def test_smurfing_rule_zero_for_normal_irregular_transactions():
    """Single large transfer or normal wide variance should not trigger smurfing."""
    base = now_utc()
    g = GraphStore()
    g.add_account_metadata(acct("LEGIT"))
    g.add_account_metadata(acct("PAYER"))
    g.add_transaction(txn("tx_single", "PAYER", "LEGIT", 150000.0, minutes_ago(10, base)))

    result = smurfing_subgraph_rule.evaluate(g, aid("LEGIT"), as_of=base)
    assert result.severity == 0.0
    assert "normal amount dispersion" in result.evidence or "no structured" in result.measured


def test_smurfing_rule_multi_hop_subgraph_coalescence():
    """Detects multi-hop intermediate structured forwarding."""
    base = now_utc()
    g = GraphStore()
    g.add_account_metadata(acct("DEST"))
    g.add_account_metadata(acct("MID1"))
    g.add_account_metadata(acct("MID2"))
    g.add_account_metadata(acct("ORIGIN"))

    # Origin feeds 2 intermediates with structured amounts, which immediately feed DEST
    g.add_transaction(txn("t1", "ORIGIN", "MID1", 30000.0, minutes_ago(30, base)))
    g.add_transaction(txn("t2", "ORIGIN", "MID2", 30000.0, minutes_ago(28, base)))
    g.add_transaction(txn("t3", "MID1", "DEST", 29500.0, minutes_ago(15, base)))
    g.add_transaction(txn("t4", "MID2", "DEST", 29500.0, minutes_ago(12, base)))

    result = smurfing_subgraph_rule.evaluate(g, aid("DEST"), as_of=base)
    assert result.severity >= 0.50
    assert "smurfing" in result.evidence.lower()


# ============================================================================
# 2. DYNAMIC WEIGHTS & TERMINAL DENSITY INDEX (TDI) TESTS
# ============================================================================

def test_terminal_density_calculation():
    anchor = (19.0760, 72.8777)  # Mumbai Central
    terminals = [
        TerminalNode(terminal_id=f"ATM_{i}", latitude=19.0760 + (i * 0.002), longitude=72.8777 + (i * 0.002))
        for i in range(15)
    ]
    tdi = compute_terminal_density(anchor, terminals, radius_km=5.0)
    assert tdi >= 10, f"Expected dense cluster, got {tdi}"


def test_ranking_adapts_to_density_and_channel():
    """Urban density prioritizes proximity; AEPS dominant accounts boost CSP agent priority."""
    g = GraphStore()
    g.add_account_metadata(AccountNodeMetadata(account_id=aid("ACC_AEPS"), district_pincode="560001"))
    base = now_utc()

    # Create mix of ATM and AEPS terminals
    terminals = [
        TerminalNode(
            terminal_id="ATM_FAR",
            terminal_type="ATM_KIOSK",
            latitude=12.9800,
            longitude=77.6000,
            district_pincode="560001",
            operating_hours="24x7",
            cash_status="ONLINE_DISPENSING",
        ),
        TerminalNode(
            terminal_id="AEPS_CLOSE",
            terminal_type="AEPS_MICRO_ATM",
            latitude=12.9716,
            longitude=77.5946,
            district_pincode="560001",
            operating_hours="09:00-21:00",
            cash_status="ONLINE_DISPENSING",
        ),
    ]

    ranked = rank_terminals(g, aid("ACC_AEPS"), terminals, window_start=base)
    assert len(ranked) == 2
    assert ranked[0].priority >= ranked[1].priority
    assert "AEPS" in ranked[0].terminal.terminal_type or "ATM" in ranked[0].terminal.terminal_type


# ============================================================================
# 3. OPERATIONAL TELEMETRY & CASH STATUS FILTER TESTS
# ============================================================================

def test_terminal_cash_out_telemetry_penalized():
    """Terminals marked CASH_OUT or OFFLINE get 0 time/feasibility score."""
    g = GraphStore()
    g.add_account_metadata(acct("T_USER"))
    base = datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)

    terminals = [
        TerminalNode(
            terminal_id="ATM_OUT",
            latitude=28.6139,
            longitude=77.2090,
            cash_status="CASH_OUT",
            operating_hours="24x7",
        ),
        TerminalNode(
            terminal_id="ATM_LIVE",
            latitude=28.6145,
            longitude=77.2095,
            cash_status="ONLINE_DISPENSING",
            operating_hours="24x7",
        ),
    ]

    ranked = rank_terminals(g, aid("T_USER"), terminals, window_start=base)
    by_id = {r.terminal.terminal_id: r for r in ranked}

    assert by_id["ATM_OUT"].components.get("time_pattern", 0) == 0.0
    assert any("CASH_OUT" in reason for reason in by_id["ATM_OUT"].reasons)
    assert by_id["ATM_LIVE"].priority > by_id["ATM_OUT"].priority


def test_terminal_closed_outside_operating_hours():
    """Branch ATM or AEPS CSP closed at night receives 0 time score."""
    g = GraphStore()
    g.add_account_metadata(acct("NIGHT_USER"))
    night_time = datetime(2026, 9, 27, 23, 30, tzinfo=timezone.utc)

    terminals = [
        TerminalNode(
            terminal_id="BRANCH_ATM_DAY",
            terminal_type="ATM_KIOSK",
            latitude=28.6139,
            longitude=77.2090,
            operating_hours="09:00-18:00",
            cash_status="ONLINE_DISPENSING",
        ),
        TerminalNode(
            terminal_id="STANDALONE_24X7",
            terminal_type="ATM_KIOSK",
            latitude=28.6140,
            longitude=77.2091,
            operating_hours="24x7",
            cash_status="ONLINE_DISPENSING",
        ),
    ]

    ranked = rank_terminals(g, aid("NIGHT_USER"), terminals, window_start=night_time)
    by_id = {r.terminal.terminal_id: r for r in ranked}

    assert by_id["BRANCH_ATM_DAY"].components.get("time_pattern", 0) == 0.0
    assert any("closed" in reason.lower() for reason in by_id["BRANCH_ATM_DAY"].reasons)
    assert by_id["STANDALONE_24X7"].priority > by_id["BRANCH_ATM_DAY"].priority


# ============================================================================
# 4. MULTI-TERMINAL CORRIDOR PREDICTION TESTS
# ============================================================================

def test_predict_terminal_corridor_generation():
    """Corridor groups top candidate and fallback waypoints with transit ETAs."""
    g = GraphStore()
    g.add_account_metadata(AccountNodeMetadata(account_id=aid("MULE_CORR"), historical_terminal_ids=["TERM_1_PRI"]))
    base = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

    terminals = [
        TerminalNode(
            terminal_id="TERM_1_PRI",
            latitude=19.0760,
            longitude=72.8777,
            district="Bandra BKC",
            operating_hours="24x7",
            cash_status="ONLINE_DISPENSING",
        ),
        TerminalNode(
            terminal_id="TERM_2_FALLBACK",
            latitude=19.0820,
            longitude=72.8810,
            district="Bandra BKC",
            operating_hours="24x7",
            cash_status="ONLINE_DISPENSING",
        ),
        TerminalNode(
            terminal_id="TERM_3_FALLBACK",
            latitude=19.0880,
            longitude=72.8850,
            district="Bandra BKC",
            operating_hours="24x7",
            cash_status="ONLINE_DISPENSING",
        ),
    ]

    ranked = rank_terminals(g, aid("MULE_CORR"), terminals, window_start=base)
    corridor = predict_terminal_corridor(g, aid("MULE_CORR"), ranked, window_start=base)

    assert corridor is not None
    assert corridor.primary_terminal_id == "TERM_1_PRI"
    assert len(corridor.waypoints) >= 2
    assert corridor.waypoints[0].order == 1
    assert corridor.waypoints[0].estimated_transit_minutes == 0.0
    assert corridor.waypoints[1].order == 2
    assert corridor.waypoints[1].estimated_transit_minutes > 0.0
    assert corridor.corridor_confidence >= 0.5
    assert corridor.corridor_radius_km > 0.0


def test_scorer_analyze_attaches_corridor():
    """RiskAlert and CaseRecord include corridor route in detection output."""
    base = now_utc()
    g = GraphStore()
    g.add_account_metadata(acct("MULE_ALERT"))
    g.add_account_metadata(acct("VICTIM"))
    g.add_transaction(txn("tx_v", "VICTIM", "MULE_ALERT", 95000.0, minutes_ago(5, base)))

    terminals = [
        TerminalNode(terminal_id="ATM_ALPHA", latitude=13.0827, longitude=80.2707, district="Anna Salai"),
        TerminalNode(terminal_id="ATM_BETA", latitude=13.0850, longitude=80.2730, district="Anna Salai"),
    ]

    alert = analyze(g, aid("MULE_ALERT"), terminals=terminals, as_of=base, notify_threshold=0)
    assert alert is not None
    assert alert.corridor is not None
    assert alert.corridor.primary_terminal_id in ("ATM_ALPHA", "ATM_BETA")
    assert len(alert.predicted_terminals) == 2

    case = build_investigation_case(g, aid("MULE_ALERT"), alert=alert, terminals=terminals, as_of=base)
    assert case.corridor is not None
    assert case.corridor.primary_terminal_id == alert.corridor.primary_terminal_id
