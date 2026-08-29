"""Unit tests for the heuristic rules + score combination (tests/test_rules.py)."""
from __future__ import annotations

from datetime import timedelta

from tests.helpers import acct, aid, graph_with, minutes_ago, now_utc, txn

from detection.rules import account_age_rule, amount_movement_rule, device_fingerprint_rule
from detection.rules import fan_in_rule, fan_out_rule, layering_rule
from detection.rules import terminal_affinity_rule, velocity_rule
from detection.scorer import evaluate_account


def test_fan_in_rule_high_when_many_senders():
    base = now_utc()
    srcs = [f"S{i:02d}" for i in range(8)]
    g = graph_with(
        [txn(f"t{i}", s, "D", 10000, minutes_ago(5, base)) for i, s in enumerate(srcs)])
    r = fan_in_rule.evaluate(g, aid("D"), as_of=base)
    assert r.severity == 1.0
    assert "8 distinct account(s)" in r.measured


def test_fan_in_rule_low_for_single_sender():
    base = now_utc()
    g = graph_with([txn("t1", "A", "D", 10000, minutes_ago(5, base))])
    r = fan_in_rule.evaluate(g, aid("D"), as_of=base)
    assert r.severity == 0.0


def test_fan_out_rule_high():
    base = now_utc()
    tgts = [f"T{i:02d}" for i in range(8)]
    g = graph_with(
        [txn(f"t{i}", "A", t, 5000, minutes_ago(5, base)) for i, t in enumerate(tgts)])
    r = fan_out_rule.evaluate(g, aid("A"), as_of=base)
    assert r.severity == 1.0


def test_velocity_rule_high_for_rapid_pass_through():
    base = now_utc()
    g = graph_with([
        txn("t1", "A", "B", 100000, minutes_ago(10, base)),
        txn("t2", "B", "C", 95000, minutes_ago(10, base) + timedelta(minutes=1)),
    ])
    r = velocity_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity == 1.0


def test_velocity_rule_low_for_slow_movement():
    base = now_utc()
    g = graph_with([
        txn("t1", "A", "B", 100000, minutes_ago(3 * 24 * 60, base)),
        txn("t2", "B", "C", 95000, minutes_ago(3 * 24 * 60, base) + timedelta(days=3)),
    ])
    r = velocity_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity == 0.0


def test_layering_rule_high_for_long_chain():
    base = now_utc()
    chain = ["V", "M1", "M2", "M3", "M4", "D"]
    g = graph_with([
        txn(f"t{i}", a, b, 90000 - i * 1000, minutes_ago(5 - i, base))
        for i, (a, b) in enumerate(zip(chain, chain[1:]))
    ])
    r = layering_rule.evaluate(g, aid("D"), as_of=base)
    assert r.severity == 1.0
    assert r.measured.startswith("longest incoming trail depth = 5")


def test_amount_movement_rule_high_for_onward_flow():
    base = now_utc()
    g = graph_with([
        txn("t1", "A", "B", 100000, minutes_ago(10, base)),
        txn("t2", "B", "C", 95000, minutes_ago(9, base)),
    ])
    r = amount_movement_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity == 1.0
    assert "95%" in r.measured


def test_account_age_rule_thresholds():
    base = now_utc()
    g = graph_with([], metas=[acct("NEW", age=3), acct("OLD", age=400)])
    assert account_age_rule.evaluate(g, aid("NEW"), as_of=base).severity == 1.0
    assert account_age_rule.evaluate(g, aid("OLD"), as_of=base).severity == 0.0
    unknown = graph_with([])  # no metadata
    assert account_age_rule.evaluate(unknown, aid("NEW"), as_of=base).severity == 0.0


def test_device_fingerprint_rule_shared_cluster():
    base = now_utc()
    g = graph_with([
        txn("t1", "A", "B", 100, minutes_ago(5, base), device="DEV-X"),
        txn("t2", "C", "B", 100, minutes_ago(4, base), device="DEV-X"),
        txn("t3", "D", "B", 100, minutes_ago(3, base), device="DEV-X"),
        txn("t4", "E", "B", 100, minutes_ago(2, base), device="DEV-X"),
        txn("t5", "F", "B", 100, minutes_ago(1, base), device="DEV-X"),
    ])
    r = device_fingerprint_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity == 1.0
    assert "5" in r.measured


def test_terminal_affinity_rule_sees_history():
    base = now_utc()
    g = graph_with(
        [txn("t1", "A", "B", 100, minutes_ago(5, base))],
        metas=[acct("A", terminals=["ATM-001", "ATM-002", "ATM-003"]),
               acct("B", terminals=["ATM-001"])])
    r = terminal_affinity_rule.evaluate(g, aid("B"), as_of=base)
    assert r.severity > 0.0
    assert "ATM-001" in r.measured


def test_scorer_combines_signals_into_high_risk():
    """A textbook aggregator profile should cross the HIGH band (>=60/100)."""
    base = now_utc()
    srcs = [f"S{i:02d}" for i in range(8)]
    events = [txn(f"in{i}", s, "AGG", 20000, minutes_ago(5, base)) for i, s in enumerate(srcs)]
    events.append(txn("out1", "AGG", "CASH", 195000, minutes_ago(4, base)))
    g = graph_with(events, metas=[acct("AGG", age=4, terminals=["ATM-001", "ATM-002"])])
    ev = evaluate_account(g, aid("AGG"), as_of=base)
    assert ev.score >= 60.0, ev
    assert ev.band in {"HIGH", "CRITICAL"}
    assert len(ev.evidence) >= 4  # several signals fired and are explainable


def test_scorer_stays_low_for_boring_account():
    base = now_utc()
    g = graph_with(
        [txn("t1", "EMPLOYER", "ME", 50000, minutes_ago(6 * 24 * 60, base))],
        metas=[acct("ME", tier="victim", age=1500)])
    ev = evaluate_account(g, aid("ME"), as_of=base)
    assert ev.score < 30.0, ev
    assert ev.band == "LOW"