"""Identity-cluster rule: many accounts registered under one shared KYC
identifier (stolen/purchased PAN, phone number, or address) — the "12-20 mule
accounts opened on unaware people's names" pattern from the mentor review.

Deliberately a SEPARATE signal from device_fingerprint_rule: device sharing
catches "same phone used to operate many accounts", this rule catches "same
underlying identity/KYC document used to *open* many accounts" -- the accounts
may later be operated from different devices, which is exactly what makes a
professionally-run mule ring harder to catch on device signals alone.
"""
from __future__ import annotations

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult, count_bins


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    """Severity from how many OTHER accounts share this account's KYC identity.

    0 -> 0.0 | 1-2 -> 0.3 | 3-7 -> 0.6 | 8+ (matches the mentor's "12-20
    accounts on one identity" scenario) -> 1.0

    Shared identity only *contributes* to risk; it is not proof the account
    holder is complicit (their identity may have been stolen/misused).
    """
    sharers = graph.accounts_sharing_kyc_identity(account_id)
    n = len(sharers)
    severity = count_bins(n, [(0, 0.0), (1, 0.3), (3, 0.6), (8, 1.0)])
    measured = f"KYC identity shared with {n} other account(s)"
    evidence = (
        f"Identity cluster: {n + 1} accounts (including {account_id}) share one KYC "
        f"identity — consistent with a mule ring opened on a single stolen/purchased "
        f"identity" if n >= 3 else
        f"Identity cluster: KYC identity shared with {n} other account(s) (not yet significant)"
    )
    return RuleResult("identity_cluster", severity, measured, evidence).clamped()
