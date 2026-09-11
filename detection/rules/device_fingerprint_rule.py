"""Device-fingerprint rule: many accounts tied to one device is a mule-cluster signal."""
from __future__ import annotations

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult, count_bins


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    """Severity from how many OTHER accounts share this account's device fingerprint.

    0 -> 0.0 | 1 -> 0.2 | 2-4 -> 0.6 | 5+ -> 1.0
    Shared device only *contributes* to risk; it is not treated as proof.
    """
    sharers = graph.accounts_sharing_device_fingerprint(account_id)
    n = len(sharers)
    severity = count_bins(n, [(0, 0.0), (1, 0.2), (2, 0.6), (5, 1.0)])
    measured = f"device fingerprint shared with {n} other account(s)"
    evidence = (f"Device: {account_id} shares a device fingerprint with {n} other "
                f"account(s)" if n >= 2 else
                f"Device: no meaningful fingerprint sharing ({n} account(s))")
    return RuleResult("device_fingerprint", severity, measured, evidence).clamped()