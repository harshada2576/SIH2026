"""Smurfing & subgraph structuring rule: detects structured micro-smurfing amounts below velocity thresholds across multi-hop subgraphs."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from pipeline.graph_store import GraphStore, _as_utc, utcnow
from detection.rules.base import RuleResult, count_bins


def _compute_mean_and_cv(amounts: List[float]) -> Tuple[float, float]:
    """Calculate mean and coefficient of variation (CV = std / mean)."""
    if not amounts:
        return 0.0, 1.0
    n = len(amounts)
    mean = sum(amounts) / n
    if mean <= 0 or n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in amounts) / (n - 1)
    std_dev = math.sqrt(variance)
    cv = std_dev / mean
    return mean, cv


def evaluate(
    graph: GraphStore,
    account_id: str,
    window_seconds: int = 3600,
    as_of: Optional[datetime] = None,
) -> RuleResult:
    """Evaluate multi-hop subgraph smurfing & structured micro-transactions.
    
    Adversaries split large amounts into structured sub-threshold transfers
    (e.g., ₹10,000 - ₹49,500) spaced across 1-2 hop intermediate nodes to evade
    per-transaction velocity rules.
    """
    if not graph.has_account(account_id):
        return RuleResult(
            "smurfing_subgraph", 0.0, "account not found in graph",
            "Smurfing: account has no observed transaction graph in this window"
        ).clamped()

    as_of_dt = _as_utc(as_of) if as_of is not None else utcnow()
    txns = graph.transactions_involving(account_id, window_seconds=window_seconds, direction="both", as_of=as_of_dt)

    if not txns:
        return RuleResult(
            "smurfing_subgraph", 0.0, "0 transactions in window",
            "Smurfing: no transactions observed in the evaluation window"
        ).clamped()

    # 1. Inspect direct transactions touching this account
    in_txns = [t for t in txns if t.target_account_id == account_id]
    out_txns = [t for t in txns if t.source_account_id == account_id]

    # Analyze structured amounts (₹5,000 to ₹49,999 - common mule structuring corridor)
    structured_in = [t for t in in_txns if 5000.0 <= t.amount_inr < 50000.0]
    structured_out = [t for t in out_txns if 5000.0 <= t.amount_inr < 50000.0]
    structured_all = structured_in + structured_out

    # 2. Check 1-hop upstream and downstream multi-hop structuring
    neighborhood = graph.get_neighborhood(account_id, degrees=1)
    nbr_structured_count = 0
    nbr_total_structured_amount = 0.0
    for nbr in neighborhood:
        nbr_txns = graph.transactions_involving(nbr, window_seconds=window_seconds, direction="both", as_of=as_of_dt)
        for nt in nbr_txns:
            if nt.transaction_id not in {t.transaction_id for t in txns}:
                if 5000.0 <= nt.amount_inr < 50000.0:
                    nbr_structured_count += 1
                    nbr_total_structured_amount += nt.amount_inr

    total_structured_txs = len(structured_all)
    all_structured_amounts = [t.amount_inr for t in structured_all]
    mean_amt, cv = _compute_mean_and_cv(all_structured_amounts)
    total_structured_amount = sum(all_structured_amounts)

    # Time span of structured transactions
    if structured_all:
        timestamps = [t.timestamp_utc for t in structured_all]
        time_span_minutes = max(1.0, (max(timestamps) - min(timestamps)).total_seconds() / 60.0)
    else:
        time_span_minutes = 60.0

    # Scoring heuristic
    severity = 0.0
    if total_structured_txs >= 4 and cv <= 0.35 and time_span_minutes <= 45:
        # High confidence smurfing ring: many structured transfers with uniform amounts in short time
        severity = 1.0
    elif total_structured_txs >= 3 and (cv <= 0.40 or nbr_structured_count >= 2):
        severity = 0.75
    elif total_structured_txs >= 2 and total_structured_amount >= 30000.0 and cv <= 0.25:
        severity = 0.50
    elif total_structured_txs >= 2 or (total_structured_txs >= 1 and nbr_structured_count >= 3):
        severity = 0.30
    elif total_structured_txs == 1 and total_structured_amount >= 20000.0:
        severity = 0.15
    else:
        severity = 0.0

    # Build measured string
    if total_structured_txs > 0:
        measured = (
            f"{total_structured_txs} structured transfer(s) (avg ₹{mean_amt:,.0f}, CV {cv:.2f}) "
            f"totaling ₹{total_structured_amount:,.0f} across {int(time_span_minutes)}m"
        )
        if nbr_structured_count > 0:
            measured += f" (+{nbr_structured_count} nbr transfers)"
    else:
        measured = "no structured smurfing amounts detected (<₹50k uniform corridor)"

    # Build explainable evidence string
    if severity >= 0.7:
        evidence = (
            f"Smurfing: {total_structured_txs} structured micro-transfers (avg ₹{mean_amt:,.0f}, CV {cv:.2f}) "
            f"totaling ₹{total_structured_amount:,.0f} moved in {int(time_span_minutes)} mins "
            f"across {len(neighborhood)} connected cluster account(s)"
        )
    elif severity >= 0.3:
        evidence = (
            f"Smurfing: {total_structured_txs} sub-threshold transfers (avg ₹{mean_amt:,.0f}) "
            f"observed within {int(time_span_minutes)} mins"
        )
    else:
        evidence = "Smurfing: transaction pattern shows normal amount dispersion (no sub-threshold clustering)"

    return RuleResult("smurfing_subgraph", severity, measured, evidence).clamped()
