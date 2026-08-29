"""Terminal ranking + end-to-end smoke (produce -> graph -> detect -> alert),
without Kafka (that is the integration-day wiring task)."""
from __future__ import annotations

from tests.helpers import acct, aid, graph_with, minutes_ago, now_utc, txn

from detection.alert_dispatcher import dispatch
from detection.scorer import analyze
from detection.terminal_ranking import rank_terminals
from shared.schemas import TerminalNode


def _terminals():
    """Two districts; T1 close & historical, T2 far & historical, T3 unrelated."""
    return [
        TerminalNode(terminal_id="ATM-001", terminal_type="ATM_KIOSK",
                     latitude=28.60, longitude=77.20, district_pincode="110001"),
        TerminalNode(terminal_id="ATM-002", terminal_type="ATM_KIOSK",
                     latitude=28.57, longitude=77.32, district_pincode="201301"),
        TerminalNode(terminal_id="POS-001", terminal_type="POS",
                     latitude=28.61, longitude=77.19, district_pincode="110001"),
    ]


def test_rank_terminals_puts_historical_close_terminal_first():
    base = now_utc()
    g = graph_with([txn("t1", "EMPLOYER", "ME", 50000, minutes_ago(5, base))],
                   metas=[acct("ME", pincode="110001", terminals=["ATM-001", "ATM-002"])])
    ranked = rank_terminals(g, aid("ME"), _terminals(), window_start=base)
    assert ranked[0].terminal.terminal_id == "ATM-001"  # same district + history
    assert ranked[0].priority > ranked[-1].priority


def test_analyze_returns_alert_for_high_risk_trail():
    base = now_utc()
    chain = ["VICTIM", "M1", "M2", "AGG"]
    events = [txn(f"t{i}", a, b, 90000 - i * 5000, minutes_ago(5 - i, base))
              for i, (a, b) in enumerate(zip(chain, chain[1:]))]
    events += [txn(f"in{i}", f"S{i:02d}", "AGG", 15000, minutes_ago(4, base)) for i in range(6)]
    events.append(txn("cashout", "AGG", "ACC-CASH", 240000, minutes_ago(3, base)))
    g = graph_with(events, metas=[acct("AGG", age=5, pincode="110001",
                                       terminals=["ATM-001", "ATM-002"])])
    alert = analyze(g, aid("AGG"), terminals=_terminals(), as_of=base)
    assert alert is not None
    assert alert.risk_score >= 0.6
    assert alert.flagged_account_id == aid("AGG")
    assert alert.evidence  # explainability strings generated from rules that fired
    assert alert.predicted_terminals  # ranked list is populated
    probs = [t.probability for t in alert.predicted_terminals]
    assert probs == sorted(probs, reverse=True)
    assert alert.predicted_window_start < alert.predicted_window_end
    assert "Money trail:" in alert.evidence[0]


def test_analyze_returns_none_below_threshold():
    base = now_utc()
    g = graph_with([txn("t1", "EMPLOYER", "ME", 50000, minutes_ago(5, base))],
                   metas=[acct("ME", tier="victim", age=1500)])
    assert analyze(g, aid("ME"), terminals=_terminals(), as_of=base) is None


def test_end_to_end_smoke_with_dispatch(capsys):
    """Produce events -> graph -> analyze -> dispatch (prints investigator alert)."""
    base = now_utc()
    chain = ["VICTIM", "M1", "M2", "AGG"]
    events = [txn(f"t{i}", a, b, 90000 - i * 5000, minutes_ago(5 - i, base))
              for i, (a, b) in enumerate(zip(chain, chain[1:]))]
    events += [txn(f"in{i}", f"S{i:02d}", "AGG", 15000, minutes_ago(4, base)) for i in range(6)]
    events.append(txn("cashout", "AGG", "ACC-CASH", 240000, minutes_ago(3, base)))
    g = graph_with(events, metas=[acct("AGG", age=5, pincode="110001",
                                       terminals=["ATM-001", "ATM-002"])])
    alert = analyze(g, aid("AGG"), terminals=_terminals(), as_of=base)
    assert alert is not None
    dispatch(alert)
    out = capsys.readouterr().out
    assert "ALERT" in out
    assert alert.complaint_id in out
    assert "PREDICTED CASH-OUT" in out