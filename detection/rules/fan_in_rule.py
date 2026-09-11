"""Fan-in rule: many accounts sending money into one account (aggregation signal)."""
from __future__ import annotations

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult, count_bins


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    """Severity from how many distinct accounts paid into this account in the window.

    Thresholds (tunable prototype choices, not banking rules):
      1-2 senders -> 0.0 | 3-4 -> 0.5 | 5-7 -> 0.75 | 8+ -> 1.0
    """
    n = graph.fan_in_count(account_id, window_seconds, as_of)
    severity = count_bins(n, [(2, 0.0), (4, 0.5), (7, 0.75), (8, 1.0)])
    measured = f"{n} distinct account(s) sent money in within {window_seconds}s"
    evidence = (f"Fan-in: {n} accounts paid into {account_id} within "
                f"{window_seconds} seconds" if n >= 3 else
                f"Fan-in: only {n} incoming sender(s) in the window (not significant)")
    return RuleResult("fan_in", severity, measured, evidence).clamped()