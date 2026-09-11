"""detection/scorer.py — Explainable heuristic scorer & terminal egress prioritization.

Combines:
1. 8 independent heuristic rules over the in-memory graph (velocity, fan-in, fan-out, layering depth, amount movement, account age, device fingerprint, terminal affinity).
2. Terminal priority ranking & predictive cash-out time window estimation.
3. Signal scoring and Kafka streaming daemon mode.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from detection.confidence import compute_confidence
from detection.rules import RULES
from detection.rules.base import RuleResult
from detection.terminal_ranking import TerminalScore, rank_terminals
from pipeline.graph_store import GraphStore, utcnow, _as_utc
from shared.schemas import PredictedTerminal, RiskAlert, TerminalNode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("scorer")

REPO_ROOT = Path(__file__).resolve().parent.parent

# Rule weights sum to 100.
# Phase 2 (2026-09): added geo_velocity, identity_cluster, ml_anomaly and
# rebalanced the original 8 weights downward proportionally to make room,
# rather than letting the total exceed 100 (evaluate_account() clamps at 100
# regardless, but an un-rebalanced table makes individual rule contributions
# harder to reason about in the evidence panel).
WEIGHTS: Dict[str, int] = {
    "velocity": 16,
    "fan_in": 16,
    "fan_out": 8,
    "layering": 10,
    "amount_movement": 10,
    "account_age": 4,
    "device_fingerprint": 4,
    "terminal_affinity": 8,
    "geo_velocity": 12,       # physically-impossible travel — strong, rare signal
    "identity_cluster": 4,    # contributing signal, like device_fingerprint
    "ml_anomaly": 8,          # unsupervised outlier score, hybrid rule+ML layer
}

RISK_BANDS: List[Tuple[int, str]] = [
    (0, "LOW"),
    (30, "MEDIUM"),
    (60, "HIGH"),
    (80, "CRITICAL"),
]

CHANNEL_WINDOW_MINUTES: Dict[str, int] = {
    "UPI": 30,
    "IMPS": 45,
    "AEPS": 15,
    "NEFT": 120,
    "RTGS": 180,
}

ALERT_THRESHOLD = 60  # Raw score >= 60 (HIGH/CRITICAL) produces an alert


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
        result: RuleResult = rule_fn(graph, account_id, window_seconds=window_seconds, as_of=as_of)
        p = result.severity * weights.get(name, 0)
        snaps.append(
            RuleSnapshot(
                name=name,
                severity=result.severity,
                points=round(p, 1),
                weight=weights.get(name, 0),
                measured=result.measured,
                evidence=result.evidence,
            )
        )
    score = min(100.0, sum(s.points for s in snaps))
    evidence = [s.evidence for s in snaps if s.severity > 0 and s.evidence]
    return AccountEvaluation(
        account_id=account_id,
        score=round(score, 1),
        band=risk_band(score),
        rules=snaps,
        evidence=evidence,
    )


def predicted_window(
    graph: GraphStore, account_id: str, as_of: Optional[datetime] = None
) -> Tuple[datetime, datetime]:
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


def reconstruct_trail(graph: GraphStore, account_id: str, max_hops: int = 6) -> List[str]:
    """Greedy backward walk returning [victim ... aggregator]."""
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


def default_terminal_path() -> str:
    """Return default path to terminals.json reference data."""
    return str(REPO_ROOT / "shared" / "terminals.json")


def load_terminals(path: Optional[str] = None) -> List[TerminalNode]:
    """Load static terminal nodes from JSON or CSV reference data."""
    json_path = Path(path or default_terminal_path())
    if json_path.exists():
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
            return [TerminalNode.from_dict(row) for row in data]

    # Fallback to CSV
    csv_path = REPO_ROOT / "data" / "output" / "terminals.csv"
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [TerminalNode.from_dict(row) for row in reader]

    return []


_complaint_counter = [0]


def _next_complaint_id(as_of: Optional[datetime] = None) -> str:
    """Generate sequential CMP-YYYY-NNNNNN complaint id."""
    _complaint_counter[0] += 1
    year = (as_of or utcnow()).year
    return f"CMP-{year}-{_complaint_counter[0]:06d}"


def analyze(
    graph: GraphStore,
    account_id: str,
    terminals: Optional[List[TerminalNode]] = None,
    window_seconds: int = 3600,
    notify_threshold: int = ALERT_THRESHOLD,
    as_of: Optional[datetime] = None,
) -> Optional[RiskAlert]:
    """Score an account, rank terminals, and build a RiskAlert if threshold is crossed."""
    ev = evaluate_account(graph, account_id, window_seconds, as_of)
    if ev.score < notify_threshold:
        return None

    term_list = terminals if terminals is not None else load_terminals()
    ws, we = predicted_window(graph, account_id, as_of)
    ranked = rank_terminals(graph, account_id, term_list, ws)

    evidence = list(ev.evidence)
    trail = reconstruct_trail(graph, account_id)
    if len(trail) > 1:
        evidence.insert(0, "Money trail: " + " -> ".join(trail))
    if ranked:
        top = ranked[0]
        evidence.append(
            f"Top cash-out candidate {top.terminal.terminal_id} (priority "
            f"{top.priority:.0f}/100) because {', '.join(top.reasons)}"
        )

    predicted = [
        PredictedTerminal(
            terminal_id=s.terminal.terminal_id,
            probability=round(s.priority / 100.0, 3),
            latitude=s.terminal.latitude,
            longitude=s.terminal.longitude,
        )
        for s in ranked
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
        confidence=compute_confidence(ev),
    )


# ============================================================================
# MODULAR SIGNAL EVALUATORS & KAFKA STREAMING HELPERS
# ============================================================================

def evaluate_fan_in_rule(signal: dict) -> tuple[float, Optional[str]]:
    """Evaluates fan-in from a graph signal."""
    fan_in = signal.get("fan_in_count", 0)
    if fan_in >= 3:
        score = 0.70 + 0.30 * min(fan_in - 3, 2) / 2.0
        evidence = f"Rapid fan-in: {fan_in} accounts transferred funds within the 5-minute window"
        return round(min(score, 1.0), 3), evidence
    return 0.0, None


def evaluate_fan_out_rule(signal: dict) -> tuple[float, Optional[str]]:
    """Evaluates fan-out from a graph signal."""
    fan_out = signal.get("fan_out_count", 0)
    if fan_out >= 3:
        score = 0.70 + 0.30 * min(fan_out - 3, 2) / 2.0
        evidence = f"Rapid fan-out: Dispersed funds to {fan_out} accounts within the 5-minute window"
        return round(min(score, 1.0), 3), evidence
    return 0.0, None


def evaluate_layering_rule(signal: dict) -> tuple[float, Optional[str]]:
    """Evaluates layering depth from a graph signal."""
    depth = signal.get("chain_depth", 0)
    active_in_window = (signal.get("fan_in_count", 0) >= 1 or signal.get("fan_out_count", 0) >= 1)
    if depth >= 3 and active_in_window:
        return 0.95, "Multi-hop layering: Account sits at depth 3+ in an active transaction chain (aggregator node)"
    elif depth == 2 and active_in_window:
        return 0.75, "Intermediate layering: Account is a pass-through node (depth 2) in a rapid multi-hop chain"
    return 0.0, None


def evaluate_device_rule(signal: dict) -> tuple[float, Optional[str]]:
    """Evaluates device reuse from a graph signal."""
    shared = signal.get("shared_device_accounts", [])
    if shared:
        return 0.90, f"Device reuse: Hardware fingerprint shared with {len(shared)} other sending account(s)"
    return 0.0, None


def evaluate_all_rules(signal: dict) -> list[tuple[float, Optional[str]]]:
    return [
        evaluate_fan_in_rule(signal),
        evaluate_fan_out_rule(signal),
        evaluate_layering_rule(signal),
        evaluate_device_rule(signal),
    ]


def score_signal(signal: dict) -> float:
    """Dominant-rule scoring over graph_signals payload."""
    rule_results = evaluate_all_rules(signal)
    rule_scores = [score for score, _ in rule_results if score > 0.0]
    if not rule_scores:
        bg = 0.05 * min(signal.get("distinct_counterparties", 0), 2) + 0.04 * min(signal.get("chain_depth", 0), 1)
        return round(min(bg, 0.25), 3)
    dominant_score = max(rule_scores)
    synergy_boost = 0.05 if len(rule_scores) > 1 else 0.0
    return round(min(dominant_score + synergy_boost, 1.0), 3)


def build_evidence(signal: dict) -> list[str]:
    """Extract evidence strings for signal."""
    rule_results = evaluate_all_rules(signal)
    evidence = [ev for score, ev in rule_results if score >= 0.50 and ev is not None]
    return evidence or ["Elevated structural activity, below strong-evidence thresholds"]


_terminal_coords_cache: Dict[str, Dict[str, Optional[float]]] = {}


def predict_terminals(signal: dict) -> list[dict]:
    """Predicts likely cash-out terminals from historical affinity with coordinates."""
    global _terminal_coords_cache
    terminals = signal.get("historical_terminal_ids", [])
    if not terminals:
        return []

    if not _terminal_coords_cache:
        term_nodes = load_terminals()
        _terminal_coords_cache = {
            t.terminal_id: {"latitude": t.latitude, "longitude": t.longitude} for t in term_nodes
        }

    base = 0.9
    predictions = []
    for i, t in enumerate(terminals[:3]):
        coord = _terminal_coords_cache.get(t, {})
        pred = {
            "terminal_id": t,
            "probability": round(base * (0.7 ** i), 2),
            "latitude": coord.get("latitude", 28.60),
            "longitude": coord.get("longitude", 77.20),
        }
        predictions.append(pred)
    return predictions


def build_alert(signal: dict) -> dict:
    """Constructs locked Risk Alert JSON dictionary from signal."""
    raw_ts = signal.get("timestamp", "")
    try:
        now = _as_utc(raw_ts)
    except Exception:
        now = utcnow()

    return {
        "complaint_id": f"SYN-{uuid.uuid4().hex[:8]}",
        "risk_score": score_signal(signal),
        "flagged_account_id": signal["account_id"],
        "predicted_terminals": predict_terminals(signal),
        "evidence": build_evidence(signal),
        "predicted_window_start": now.isoformat(),
        "predicted_window_end": (now + timedelta(minutes=45)).isoformat(),
    }


def run():
    """Kafka streaming listener loop for standalone daemon execution."""
    from shared.kafka_utils import (
        KAFKA_BOOTSTRAP_SERVERS,
        GRAPH_SIGNALS_TOPIC,
        RISK_ALERTS_TOPIC,
        get_kafka_consumer,
        get_kafka_producer,
    )

    consumer = get_kafka_consumer(
        GRAPH_SIGNALS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="scorer-group",
    )
    producer = get_kafka_producer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

    log.info(f"Scorer started, listening on topic '{GRAPH_SIGNALS_TOPIC}'...")

    for message in consumer:
        if not message.value:
            continue
        signal = message.value
        score = score_signal(signal)
        if score >= 0.60:
            alert = build_alert(signal)
            producer.send(RISK_ALERTS_TOPIC, value=alert)
            log.info(f"ALERT dispatched: {alert['complaint_id']} for {alert['flagged_account_id']} (score: {alert['risk_score']})")


if __name__ == "__main__":
    try:
        run()
    except ConnectionError as e:
        print(f"\n[!] {e}\n")
        sys.exit(0)

