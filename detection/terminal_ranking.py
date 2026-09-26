"""Candidate cash-out terminal ranking (the "where should we look first" layer).

Combines history / distance / time / terminal type / network association /
district relevance into a 0-100 PRIORITY per terminal. These are investigative
priorities, explicitly NOT calibrated probabilities (that would require a
trained, calibrated model — future work, PRD.md section 6).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Dict, List, Optional, Tuple

from detection.rules.terminal_affinity_rule import network_terminal_frequency
from pipeline.graph_store import GraphStore, utcnow
from shared.schemas import AccountNodeMetadata, TerminalNode

# Terminal ranking sub-weights (sum == 100) — the "what matters for cash-out"
# policy layer, tunable per prototype.
TERMINAL_RANK_WEIGHTS: Dict[str, int] = {
    "history": 30, "distance": 20, "time_pattern": 15,
    "terminal_type": 10, "network_association": 15, "district_relevance": 10,
}


@dataclass
class TerminalScore:
    """One ranked cash-out candidate."""

    terminal: TerminalNode
    priority: float  # 0..100 priority, NOT a calibrated probability
    components: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometres."""
    r = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dlat = p2 - p1
    dlon = radians(lon2) - radians(lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _anchor_point(graph: GraphStore, account_id: str,
                  terminals: List[TerminalNode]) -> Optional[Tuple[float, float]]:
    """Preferred "where is this account operating" point, in priority order:
    1. centroid of its historical terminals, 2. centroid of its district's
    terminals, 3. centroid of all terminals (used when nothing else is known)."""
    if not terminals:
        return None
    by_id = {t.terminal_id: t for t in terminals}

    def centroid(coords: List[Tuple[float, float]]) -> Tuple[float, float]:
        return (sum(c[0] for c in coords) / len(coords),
                sum(c[1] for c in coords) / len(coords))

    hist = [by_id[t] for t in graph.historical_terminal_ids(account_id) if t in by_id]
    if hist:
        return centroid([(t.latitude, t.longitude) for t in hist])

    meta = graph.get_account_metadata(account_id)
    if meta and meta.district_pincode:
        same = [t for t in terminals if t.district_pincode == meta.district_pincode]
        if same:
            return centroid([(t.latitude, t.longitude) for t in same])

    return centroid([(t.latitude, t.longitude) for t in terminals])


def _time_pattern_score(terminal: TerminalNode, hist_freq: Counter,
                        window_start: datetime) -> float:
    """0-15: overlap between the predicted cash-out hour and typical usage hours."""
    hour = window_start.hour
    plausible = 15 if 6 <= hour <= 22 else 5  # prototype active-hours assumption
    if hist_freq.get(terminal.terminal_id, 0) > 0:
        plausible = min(15.0, plausible + 5.0)
    return plausible


def rank_terminals(
    graph: GraphStore,
    account_id: str,
    terminals: List[TerminalNode],
    window_start: Optional[datetime] = None,
) -> List[TerminalScore]:
    """Rank candidate cash-out terminals for `account_id` — highest priority first.

    Sub-scores (walls sum to 100): history 30, distance 20, time_pattern 15,
    terminal_type 10, network_association 15, district_relevance 10.
    """
    if not terminals:
        return []
    window_start = window_start or utcnow()
    anchor = _anchor_point(graph, account_id, terminals)

    freq: Counter = network_terminal_frequency(graph, account_id, degrees=1)
    members = {account_id} | graph.get_neighborhood(account_id, degrees=1)
    hist_members: Counter = Counter()
    for m in members:
        for t in set(graph.historical_terminal_ids(m)):
            hist_members[t] += 1

    meta: Optional[AccountNodeMetadata] = graph.get_account_metadata(account_id)

    candidate_terminals = terminals
    if len(terminals) > 100 and anchor:
        must_include_ids = set(freq.keys()) | set(hist_members.keys())
        pin = meta.district_pincode if (meta and meta.district_pincode) else None
        
        filtered = [
            t for t in terminals
            if t.terminal_id in must_include_ids
            or (pin and t.district_pincode == pin)
            or (abs(t.latitude - anchor[0]) < 0.50 and abs(t.longitude - anchor[1]) < 0.50)
        ]
        if len(filtered) >= 10:
            candidate_terminals = filtered
        else:
            candidate_terminals = terminals[:150]

    max_freq = max(freq.values()) if freq else 0
    max_dist = 0.0
    distances: Dict[str, float] = {}
    if anchor:
        for t in candidate_terminals:
            d = _haversine_km(anchor[0], anchor[1], t.latitude, t.longitude)
            distances[t.terminal_id] = d
            max_dist = max(max_dist, d)
    if max_dist <= 0:
        max_dist = 1.0  # guard against zero-distance division

    scores: List[TerminalScore] = []
    for t in candidate_terminals:
        c: Dict[str, float] = {}

        c["history"] = (30.0 * freq.get(t.terminal_id, 0) / max_freq) if max_freq else 0.0

        if anchor is None:
            c["distance"] = 10.0  # unknown anchor -> neutral
        else:
            d = distances.get(t.terminal_id, 0.0)
            c["distance"] = 20.0 * (1.0 - d / max_dist)

        c["time_pattern"] = _time_pattern_score(t, freq, window_start)

        c["terminal_type"] = {"AEPS_MICRO_ATM": 10.0, "ATM_KIOSK": 8.0, "POS": 4.0}.get(
            t.terminal_type, 4.0)

        n_assoc = hist_members.get(t.terminal_id, 0)
        c["network_association"] = min(15.0, n_assoc * 5.0)

        if meta and meta.district_pincode:
            c["district_relevance"] = 10.0 if t.district_pincode == meta.district_pincode else 0.0
        else:
            c["district_relevance"] = 5.0  # district unknown -> neutral

        priority = round(sum(c.values()), 1)
        reasons = [f"{k}: {v:.0f}" for k, v in c.items() if v > 0]
        scores.append(TerminalScore(terminal=t, priority=priority,
                                    components=c, reasons=reasons))

    scores.sort(key=lambda s: s.priority, reverse=True)
    return scores