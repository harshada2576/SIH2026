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
import math
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
from detection.terminal_ranking import TerminalScore, predict_terminal_corridor, rank_terminals
from pipeline.graph_store import GraphStore, utcnow, _as_utc
from shared.schemas import (
    CaseLifecycleState,
    CaseRecord,
    CorridorWaypoint,
    MoneyTrailLeg,
    PredictedTerminal,
    RiskAlert,
    SelectiveFundProtection,
    TerminalBlockRequest,
    TerminalCorridor,
    TerminalNode,
    WithdrawalAttemptEvent,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("scorer")

REPO_ROOT = Path(__file__).resolve().parent.parent

# Rule weights sum to 100.
# Phase 2 (2026-09): added geo_velocity, identity_cluster, ml_anomaly, smurfing_subgraph
# and rebalanced weights proportionally to sum to 100.
WEIGHTS: Dict[str, int] = {
    "velocity": 14,
    "fan_in": 14,
    "fan_out": 7,
    "layering": 9,
    "amount_movement": 9,
    "smurfing_subgraph": 10,  # Adversarial micro-smurfing / multi-hop structured split
    "account_age": 4,
    "device_fingerprint": 4,
    "terminal_affinity": 7,
    "geo_velocity": 10,       # physically-impossible travel — strong, rare signal
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
    corridor = predict_terminal_corridor(graph, account_id, ranked, ws)

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
    if corridor and len(corridor.waypoints) > 1:
        evidence.append(
            f"Corridor prediction: Primary {corridor.primary_terminal_id} with {len(corridor.waypoints)-1} "
            f"sequential fallback hops within {corridor.corridor_radius_km:.1f} km ({corridor.recommended_patrol_sector})"
        )

    predicted = [
        PredictedTerminal(
            terminal_id=s.terminal.terminal_id,
            probability=round(s.priority / 100.0, 3),
            latitude=s.terminal.latitude,
            longitude=s.terminal.longitude,
            terminal_type=s.terminal.terminal_type,
            cash_status=getattr(s.terminal, "cash_status", "ONLINE_DISPENSING"),
            operating_hours=getattr(s.terminal, "operating_hours", "24x7"),
            priority_score=s.priority,
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
        corridor=corridor,
    )


def build_investigation_case(
    graph: GraphStore,
    account_id: str,
    alert: Optional[RiskAlert] = None,
    terminals: Optional[List[TerminalNode]] = None,
    as_of: Optional[datetime] = None,
    complaint_id: Optional[str] = None,
) -> CaseRecord:
    """Build a rich, structured investigation case for CyberShield and persistence."""
    if alert is None:
        term_list = terminals
        if term_list is None and graph.terminals:
            term_list = [TerminalNode.from_dict(t) for t in graph.terminals.values()]
        alert = analyze(graph, account_id, terminals=term_list, as_of=as_of, notify_threshold=0)

    funds = graph.compute_account_funds(account_id, as_of=as_of)
    trail_legs = graph.reconstruct_detailed_chain(account_id, as_of=as_of)

    ev = evaluate_account(graph, account_id, as_of=as_of)
    case_id = f"CASE-{alert.complaint_id}" if alert and alert.complaint_id else f"CASE-{uuid.uuid4().hex[:8]}"

    state = CaseLifecycleState.POST_COMPLAINT_ESCALATED if complaint_id else CaseLifecycleState.PRE_COMPLAINT_INTERVENTION

    return CaseRecord(
        case_id=case_id,
        flagged_account_id=account_id,
        state=state,
        risk_score=alert.risk_score if alert else round(ev.score / 100.0, 3),
        confidence=alert.confidence if alert and alert.confidence is not None else compute_confidence(ev),
        band=ev.band,
        suspicious_amount=funds["suspicious_amount"],
        protected_amount=funds["protected_amount"],
        existing_balance=funds["existing_balance"],
        money_trail=trail_legs,
        predicted_terminals=alert.predicted_terminals if alert else [],
        corridor=alert.corridor if alert else None,
        predicted_window_start=_as_utc(alert.predicted_window_start).isoformat() if alert else utcnow().isoformat(),
        predicted_window_end=_as_utc(alert.predicted_window_end).isoformat() if alert else (utcnow() + timedelta(minutes=45)).isoformat(),
        evidence=alert.evidence if alert else list(ev.evidence),
        bank_hold_status="ACTIVE" if ev.score >= ALERT_THRESHOLD else "NONE",
        terminal_block_status="REQUESTED" if ev.score >= ALERT_THRESHOLD else "NONE",
        lea_notification_status="SENT" if ev.score >= ALERT_THRESHOLD else "NONE",
        complaint_id=complaint_id,
    )


def correlate_withdrawal_attempt(
    graph: GraphStore,
    attempt: WithdrawalAttemptEvent,
    active_cases: Optional[List[CaseRecord]] = None,
) -> Tuple[Optional[CaseRecord], Dict[str, Any]]:
    """Correlate an attempted cash-out withdrawal event with active cases and predicted terminals."""
    matched_case: Optional[CaseRecord] = None
    distance_km: Optional[float] = None
    terminal_matched = False

    active_cases = active_cases or []

    for c in active_cases:
        # Check if attempt account is the flagged account or part of the money trail
        accounts_in_case = {c.flagged_account_id}
        for leg in c.money_trail:
            accounts_in_case.add(leg.source_account_id)
            accounts_in_case.add(leg.target_account_id)

        if attempt.account_id in accounts_in_case:
            matched_case = c
            # Check terminal match or proximity
            for pred in c.predicted_terminals:
                if pred.terminal_id == attempt.terminal_id:
                    terminal_matched = True
                    distance_km = 0.0
                    break
                elif pred.latitude is not None and pred.longitude is not None:
                    # Check distance from predicted terminal
                    term_node = graph.terminals.get(attempt.terminal_id, {})
                    if term_node.get("latitude") is not None and term_node.get("longitude") is not None:
                        t_lat, t_lon = float(term_node["latitude"]), float(term_node["longitude"])
                        dlat = math.radians(t_lat - pred.latitude)
                        dlon = math.radians(t_lon - pred.longitude)
                        a = math.sin(dlat / 2)**2 + math.cos(math.radians(pred.latitude)) * math.cos(math.radians(t_lat)) * math.sin(dlon / 2)**2
                        dist = 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                        if distance_km is None or dist < distance_km:
                            distance_km = round(dist, 2)
            break

    # Get nearby locations/terminals around the attempted terminal
    nearby = graph.find_nearby_terminals(attempt.terminal_id, radius_km=5.0)
    attempt.nearby_terminals = nearby
    attempt.distance_to_predicted_km = distance_km

    # Check recurring activity for this account at this terminal
    recurrence = graph.record_account_terminal_activity(attempt.account_id, attempt.terminal_id, attempt.timestamp)

    if matched_case:
        attempt.correlated_case_id = matched_case.case_id
        # Update matched case state to CASHOUT_ATTEMPT_DETECTED if currently in PRE_COMPLAINT_INTERVENTION
        if matched_case.state == CaseLifecycleState.PRE_COMPLAINT_INTERVENTION:
            matched_case.state = CaseLifecycleState.CASHOUT_ATTEMPT_DETECTED
        matched_case.withdrawal_attempts.append(attempt.to_dict())
        matched_case.updated_at = utcnow().isoformat()

        # If terminal block is active or requested, cashout is BLOCKED/INTERCEPTED
        if matched_case.terminal_block_status in ("REQUESTED", "ACTIVE"):
            attempt.is_blocked = True
            attempt.action_taken = "BLOCKED"
        else:
            attempt.action_taken = "FLAGGED"
    else:
        attempt.action_taken = "MONITORED"

    correlation_summary = {
        "correlated": matched_case is not None,
        "case_id": matched_case.case_id if matched_case else None,
        "terminal_matched": terminal_matched,
        "distance_to_predicted_km": distance_km,
        "action_taken": attempt.action_taken,
        "is_blocked": attempt.is_blocked,
        "recurrence": recurrence,
        "nearby_terminals_count": len(nearby),
    }

    return matched_case, correlation_summary


def evaluate_repeated_targeting(
    graph: GraphStore,
    account_id: str,
    terminal_id: str,
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Evaluate and escalate risk for repeated targeting of the same physical ATM."""
    ts = timestamp or utcnow()
    return graph.record_account_terminal_activity(account_id, terminal_id, ts)



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
    run()

