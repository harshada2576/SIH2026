"""Layering rule: how many hops the money passed through to reach this account."""
from __future__ import annotations

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult, count_bins


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             max_depth: int = 8, as_of=None) -> RuleResult:
    """Severity from `trail_depth` — the longest reverse chain into the account.

    Depth 0-1 (direct only) -> 0.0 | 2 -> 0.33 | 3-4 -> 0.66 | 5+ -> 1.0
    A long chain is only a clue, never proof of fraud by itself.
    """
    depth = graph.trail_depth(account_id, window_seconds, max_depth, as_of)
    severity = count_bins(depth, [(1, 0.0), (2, 0.33), (4, 0.66), (5, 1.0)])
    measured = f"longest incoming trail depth = {depth} hop(s)"
    evidence = (f"Layering: money passed through {depth} account(s) before reaching "
                f"{account_id}" if depth >= 3 else
                f"Layering: trail depth only {depth} hop(s) (not significant)")
    return RuleResult("layering", severity, measured, evidence).clamped()