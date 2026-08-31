"""Account-age rule: newly opened accounts suddenly moving large sums are more notable."""
from __future__ import annotations

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    """Severity from `account_age_days` metadata (0 if metadata is missing).

    <7 days -> 1.0 | 7-30 -> 0.6 | 30-180 -> 0.2 | >180 -> 0.0
    A new account is ONE signal, never proof on its own.
    """
    meta = graph.get_account_metadata(account_id)
    if meta is None:
        return RuleResult(
            "account_age", 0.0, "age metadata unavailable",
            "Account age: metadata not available, no points assigned").clamped()
    age = meta.account_age_days
    if age < 7:
        severity = 1.0
    elif age < 30:
        severity = 0.6
    elif age < 180:
        severity = 0.2
    else:
        severity = 0.0
    measured = f"account age = {age} day(s)"
    evidence = (f"Account age: {account_id} is only {age} day(s) old" if severity >= 0.6 else
                f"Account age: {age} day(s) old (not a new account)")
    return RuleResult("account_age", severity, measured, evidence).clamped()