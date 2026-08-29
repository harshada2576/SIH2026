"""Velocity rule: how quickly received money is moved onward (rapid pass-through)."""
from __future__ import annotations

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    """Severity from the fastest inbound -> outbound gap at this account.

    <2 min -> 1.0 | 2-10 min -> 0.7 | 10-30 min -> 0.4 | >30 min -> 0.0
    """
    gap = graph.edge_latency_between(account_id, direction="out")
    if gap is None:
        return RuleResult(
            "velocity", 0.0, "no incoming->outgoing pair observed",
            "Velocity: no received funds were moved onward within the window").clamped()
    seconds = gap.total_seconds()
    if seconds < 120:
        severity = 1.0
    elif seconds < 600:
        severity = 0.7
    elif seconds < 1800:
        severity = 0.4
    else:
        severity = 0.0
    measured = f"fastest pass-through gap = {int(seconds)}s"
    evidence = (f"Velocity: funds moved onward within {int(seconds)} seconds of being "
                f"received" if severity >= 0.7 else
                f"Velocity: funds moved onward after {int(seconds)}s (not rapid)")
    return RuleResult("velocity", severity, measured, evidence).clamped()