"""Amount-movement rule: share of received funds that is forwarded onward (retention)."""
from __future__ import annotations

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    """Severity from `forwarded / received` ratio for the account.

    Ratio >= 0.9 -> 1.0 | 0.7-0.9 -> 0.66 | 0.5-0.7 -> 0.33 | <0.5 -> 0.0
    """
    received = [e.amount_inr for e in graph.transactions_involving(
        account_id, window_seconds, "in", as_of)]
    if not received:
        return RuleResult(
            "amount_movement", 0.0, "no inbound funds in window",
            "Amount movement: no received funds observed").clamped()
    forwarded = [e.amount_inr for e in graph.forwarded_transactions(
        account_id, window_seconds, as_of)]
    ratio = min(1.0, sum(forwarded) / sum(received))  # cap at 100% for display
    if ratio >= 0.9:
        severity = 1.0
    elif ratio >= 0.7:
        severity = 0.66
    elif ratio >= 0.5:
        severity = 0.33
    else:
        severity = 0.0
    measured = f"{ratio:.0%} of received funds (₹{sum(received):,.0f}) forwarded onward"
    evidence = (f"Amount movement: {ratio:.0%} of ₹{sum(received):,.0f} received was moved "
                f"onward" if severity >= 0.66 else
                f"Amount movement: only {ratio:.0%} of received funds forwarded (retains funds)")
    return RuleResult("amount_movement", severity, measured, evidence).clamped()