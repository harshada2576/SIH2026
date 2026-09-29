"""Terminal-affinity rule: historical cash-out behaviour of the account and its network.

Feeds BOTH (a) the account/trail risk score and (b) the terminal ranking in
detection/scorer.py — see `network_terminal_frequency()`.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult


def network_terminal_frequency(
    graph: GraphStore, account_id: str, degrees: int = 1, as_of: Optional[datetime] = None,
) -> Counter:
    """How often each terminal appears in the historical cash-outs of the account
    and its N-hop network. Returns a Counter keyed by terminal_id."""
    members = {account_id} | graph.get_neighborhood(account_id, degrees=degrees, as_of=as_of)
    freq: Counter = Counter()
    for member in members:
        freq.update(graph.historical_terminal_ids(member, as_of=as_of))
    return freq


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    """Severity from how much historical cash-out behaviour the network has.

    Frequency-weighted: 0 terminals -> 0.0 ... 3+ distinct terminals with history -> 1.0
    """
    freq = network_terminal_frequency(graph, account_id)
    count = len(freq)
    if count == 0:
        return RuleResult(
            "terminal_affinity", 0.0, "no historical cash-out data",
            "History: no prior cash-out records for this account/network").clamped()
    severity = min(1.0, count / 3.0 if count < 8 else 1.0)
    top = freq.most_common(3)
    measured = f"{count} distinct terminal(s) historically used: {', '.join(t for t, _ in top)}"
    evidence = (f"History: network has cashed out at terminal(s) {', '.join(t for t, _ in top)} "
                f"before — matching behaviour raises risk" if count >= 1 else
                "History: no historical cash-out pattern")
    return RuleResult("terminal_affinity", severity, measured, evidence).clamped()