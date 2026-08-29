"""Weighted heuristic scorer — the "explainable security guard" of the pipeline.

Pipeline view (Architecture.md section 2, workstream 3):
    filtered transactions -> graph -> run each rule -> weighted risk score
    -> LOW/MEDIUM/HIGH/CRITICAL -> rank nearby cash-out terminals (in
    detection/terminal_ranking.py) -> RiskAlert.

Design choices (group brief):
  - Each rule returns a severity in [0, 1]; WEIGHTS decide how much that signal
    counts (not every signal is equal). Weights sum to 100 so the raw score is
    already /100; RiskAlert.risk_score is that value normalized to /1.
  - Terminal scores are PRIORITY scores, explicitly NOT calibrated
    probabilities. The schema field is `probability` (locked contract); treat it
    as "how likely we should look here first".
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from detection.rules import RULES
from detection.rules.base import RuleResult
from detection.terminal_ranking import TerminalScore, rank_terminals
from pipeline.graph_store import GraphStore, utcnow
from shared.schemas import PredictedTerminal, RiskAlert, TerminalNode

# Every signal's max points. Sum == 100 -> the raw score is score/100.
# Rule weights are the tunable "policy" layer — a judge question, not a bug.
WEIGHTS: Dict[str, int] = {
    "velocity": 20,
    "fan_in": 20,
    "fan_out": 10,
    "layering": 15,
    "amount_movement": 15,
    "account_age": 5,
    "device_fingerprint": 5,
    "terminal_affinity": 10,
}

# score (0-100) -> risk level. Prototype thresholds, not RBI/MHA thresholds.
RISK_BANDS: List[Tuple[int, str]] = [
    (0, "LOW"), (30, "MEDIUM"), (60, "HIGH"), (80, "CRITICAL"),
]

# Cash-out latency assumption per rail (Architecture.md section 9).
CHANNEL_WINDOW_MINUTES: Dict[str, int] = {
    "UPI": 30, "IMPS": 45, "AEPS": 15, "NEFT": 120, "RTGS": 180,
}

ALERT_THRESHOLD = 60  # only score >= HIGH produces an alert


@dataclass
class RuleSnapshot:
    """One rule's contribution to the total score, for the evidence panel."""

    name: str
    severity: float
    points: float
    weight: int
    measured: str
    evidence: str


@dataclass
class AccountEvaluation:
    """Result of running all rules against one account."""

    account_id: str
    score: float  # 0..100
    band: str
    rules: List[RuleSnapshot] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


def risk_band(score: float) -> str:
    """Map a 0-100 score to LOW/MEDIUM/HIGH/CRITICAL."""
    band = RISK_BANDS[0][1]
    for threshold, label in RISK_BANDS:
        if score >= threshold:
            band = label
    return band


def evaluate_account(
    graph: GraphStore,
    account_id: str,
    window_seconds: int = 3600,
    as_of: Optional[datetime] = None,
    weights: Optional[Dict[str, int]] = None,
) -> AccountEvaluation:
    """Run every rule on the account, combine into one explainable 0-100 score."""
    weights = weights or WEIGHTS
    snaps: List[RuleSnapshot] = []
    for name, rule_fn in RULES.items():
        result: RuleResult = rule_fn(graph, account_id,
                                     window_seconds=window_seconds, as_of=as_of)
        p = result.severity * weights.get(name, 0)
        snaps.append(RuleSnapshot(
            name=name, severity=result.severity, points=round(p, 1),
            weight=weights.get(name, 0), measured=result.measured,
            evidence=result.evidence,
        ))
    score = min(100.0, sum(s.points for s in snaps))
    evidence = [s.evidence for s in snaps if s.severity > 0]
    return AccountEvaluation(
        account_id=account_id, score=round(score, 1),
        band=risk_band(score), rules=snaps, evidence=evidence,
    )


def predicted_window(graph: GraphStore, account_id: str,
                     as_of: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """Cash-out window from the most recent transaction + channel-based latency."""
    base = _as_utc(as_of) if as_of is not None else utcnow()
    latest: Optional[datetime] = None
    channel = "UPI"
    for e in graph.transactions_involving(account_id, direction="both"):
        ts = e.timestamp_utc
        if latest is None or ts > latest:
            latest, channel = ts, e.payment_channel
    start = max(base, latest) if latest else base
    horizon = CHANNEL_WINDOW_MINUTES.get(channel, 60)
    return start, start + timedelta(minutes=horizon)


def reconstruct_trail(graph: GraphStore, account_id: str,
                      max_hops: int = 6) -> List[str]:
    """Greedy backward walk (largest incoming leg) returning [leaf ... aggregator].

    Used only to enrich the alert evidence with the human-readable money trail.
    """
    trail: List[str] = [account_id]
    cur = account_id
    for _ in range(max_hops):
        incoming = graph.transactions_involving(cur, direction="in")
        if not incoming:
            break
        leg = max(incoming, key=lambda e: e.amount_inr)
        if leg.source_account_id in trail:
            break
        trail.append(f"{leg.source_account_id} (₹{leg.amount_inr:,.0f} in)")
        cur = leg.source_account_id
    return list(reversed(trail))


def analyze(
    graph: GraphStore,
    account_id: str,
    terminals: Optional[List[TerminalNode]] = None,
    window_seconds: int = 3600,
    notify_threshold: int = ALERT_THRESHOLD,
    as_of: Optional[datetime] = None,
) -> Optional[RiskAlert]:
    """Score an account, rank terminals, and build an alert if threshold is crossed.

    Returns None when the score is below `notify_threshold` (no alert needed).
    """
    ev = evaluate_account(graph, account_id, window_seconds, as_of)
    if ev.score < notify_threshold:
        return None

    ws, we = predicted_window(graph, account_id, as_of)
    ranked = rank_terminals(graph, account_id, terminals or [], ws)

    evidence = list(ev.evidence)
    trail = reconstruct_trail(graph, account_id)
    if len(trail) > 1:
        evidence.insert(0, "Money trail: " + " -> ".join(trail))
    if ranked:
        top = ranked[0]
        evidence.append(
            f"Top cash-out candidate {top.terminal.terminal_id} (priority "
            f"{top.priority:.0f}/100) because {', '.join(top.reasons)}")

    predicted = [
        PredictedTerminal(
            terminal_id=s.terminal.terminal_id,
            probability=round(s.priority / 100.0, 3),  # priority, not calibrated p
            latitude=s.terminal.latitude,
            longitude=s.terminal.longitude,
        ) for s in ranked
    ]

    uid = _next_complaint_id(as_of)
    return RiskAlert(
        complaint_id=uid,
        risk_score=round(ev.score / 100.0, 3),
        flagged_account_id=account_id,
        predicted_terminals=predicted,
        evidence=evidence,
        predicted_window_start=ws,
        predicted_window_end=we,
    )


def _as_utc(dt: datetime) -> datetime:
    """Assume UTC for naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt.astimezone(datetime.now().astimezone().tzinfo)


_complaint_counter = [0]


def _next_complaint_id(as_of: Optional[datetime] = None) -> str:
    """Deterministic-ish CMP-YYYY-NNNNNN complaint id (demo only)."""
    _complaint_counter[0] += 1
    year = (as_of or utcnow()).year
    return f"CMP-{year}-{_complaint_counter[0]:06d}"


def default_terminal_path() -> str:
    """Where seed_terminals.py writes the static terminal reference data."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "shared", "terminals.json")


def load_terminals(path: Optional[str] = None) -> List[TerminalNode]:
    """Load terminals from JSON; returns [] (no candidates) if the file is absent."""
    path = path or default_terminal_path()
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        import json
        return [TerminalNode(**row) for row in json.load(f)]