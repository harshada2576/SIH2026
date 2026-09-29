"""Candidate cash-out terminal ranking & multi-terminal corridor prediction.

Combines:
1. Dynamic heuristic scoring with Terminal Density Index (TDI) adapting across dense urban metros vs rural AEPS hubs.
2. Real-world operating hours & live cash depletion telemetry filtering.
3. AEPS vs ATM behavioral asymmetry (CSP float limits vs card sweep egress).
4. Multi-terminal fallback corridor route prediction (primary -> secondary -> tertiary escape routes).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Dict, List, Optional, Tuple

from detection.rules.terminal_affinity_rule import network_terminal_frequency
from pipeline.graph_store import GraphStore, utcnow
from shared.schemas import (
    AccountNodeMetadata,
    CorridorWaypoint,
    PredictedTerminal,
    TerminalCorridor,
    TerminalNode,
)

# Standard baseline weights (sum == 100)
DEFAULT_RANK_WEIGHTS: Dict[str, int] = {
    "history": 30,
    "distance": 20,
    "time_pattern": 15,
    "terminal_type": 10,
    "network_association": 15,
    "district_relevance": 10,
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
                  terminals: List[TerminalNode],
                  as_of: Optional[datetime] = None) -> Optional[Tuple[float, float]]:
    """Preferred "where is this account operating" point, in priority order:
    1. centroid of its historical terminals, 2. centroid of its district's
    terminals, 3. centroid of all terminals (used when nothing else is known)."""
    if not terminals:
        return None
    by_id = {t.terminal_id: t for t in terminals}

    def centroid(coords: List[Tuple[float, float]]) -> Tuple[float, float]:
        return (sum(c[0] for c in coords) / len(coords),
                sum(c[1] for c in coords) / len(coords))

    hist = [by_id[t] for t in graph.historical_terminal_ids(account_id, as_of=as_of) if t in by_id]
    if hist:
        return centroid([(t.latitude, t.longitude) for t in hist])

    meta = graph.get_account_metadata(account_id)
    if meta and meta.district_pincode:
        same = [t for t in terminals if t.district_pincode == meta.district_pincode]
        if same:
            return centroid([(t.latitude, t.longitude) for t in same])

    return centroid([(t.latitude, t.longitude) for t in terminals])


def compute_terminal_density(anchor: Tuple[float, float], terminals: List[TerminalNode], radius_km: float = 5.0) -> int:
    """Count terminals within radius_km to determine Terminal Density Index (TDI)."""
    return sum(1 for t in terminals if _haversine_km(anchor[0], anchor[1], t.latitude, t.longitude) <= radius_km)


def _resolve_dynamic_weights(
    tdi: int,
    account_is_aeps_dominant: bool = False
) -> Dict[str, float]:
    """Dynamically adjust ranking weights based on density and channel behavior."""
    if tdi >= 12:
        # High Density Urban Metro Hub: Proximity to fast transit & 24/7 standalone kiosks dominate
        return {
            "history": 22.0,
            "distance": 28.0,
            "time_pattern": 15.0,
            "terminal_type": 15.0,
            "network_association": 12.0,
            "district_relevance": 8.0,
        }
    elif tdi <= 4:
        # Rural / Semi-Urban Corridor: Local network ties and AEPS CSP points dominate
        weights = {
            "history": 25.0,
            "distance": 12.0,
            "time_pattern": 10.0,
            "terminal_type": 13.0,
            "network_association": 22.0,
            "district_relevance": 18.0,
        }
        if account_is_aeps_dominant:
            weights["terminal_type"] = 18.0
            weights["network_association"] = 25.0
            weights["distance"] = 9.0
        return weights
    else:
        # Balanced baseline
        return {
            "history": 30.0,
            "distance": 20.0,
            "time_pattern": 15.0,
            "terminal_type": 10.0,
            "network_association": 15.0,
            "district_relevance": 10.0,
        }


def _check_operating_hours(hours_str: str, current_time: datetime) -> bool:
    """Check if the given time falls within terminal operating hours (e.g. '24x7', '09:00-20:00')."""
    if not hours_str or hours_str.strip().lower() in ("24x7", "24/7", "all_day", "24 hours"):
        return True
    try:
        parts = hours_str.strip().split("-")
        if len(parts) == 2:
            start_h, start_m = [int(x) for x in parts[0].strip().split(":")]
            end_h, end_m = [int(x) for x in parts[1].strip().split(":")]
            curr_val = current_time.hour * 60 + current_time.minute
            start_val = start_h * 60 + start_m
            end_val = end_h * 60 + end_m
            if start_val <= end_val:
                return start_val <= curr_val <= end_val
            else:
                # Overnight hours (e.g. 20:00-06:00)
                return curr_val >= start_val or curr_val <= end_val
    except Exception:
        pass
    return True


def _telemetry_and_time_score(
    terminal: TerminalNode,
    hist_freq: Counter,
    window_start: datetime,
    max_weight: float = 15.0
) -> Tuple[float, List[str]]:
    """Evaluate real-world feasibility taking into account cash status, operating hours, and time of day."""
    reasons: List[str] = []
    hour = window_start.hour
    is_open = _check_operating_hours(terminal.operating_hours, window_start)

    # 1. Physical cash & service status filter
    cash_status = getattr(terminal, "cash_status", "ONLINE_DISPENSING")
    if cash_status in ("CASH_OUT", "OFFLINE", "MAINTENANCE"):
        reasons.append(f"Terminal telemetry: {cash_status} (infeasible)")
        return 0.0, reasons

    # 2. Operating hours filter
    if not is_open:
        reasons.append(f"Terminal closed at {window_start.strftime('%H:%M')} (hours: {terminal.operating_hours})")
        return 0.0, reasons

    # 3. Night vs Daytime feasibility
    is_night = hour < 6 or hour >= 22
    if terminal.terminal_type == "AEPS_MICRO_ATM":
        if is_night:
            score = max_weight * 0.15  # Kirana/CSP stores are rarely accessible late night
            reasons.append("AEPS CSP agent store closed/low access during late night")
        else:
            score = max_weight * 0.85
            reasons.append("AEPS CSP agent store open for biometric cash-out")
    elif terminal.terminal_type == "ATM_KIOSK":
        if is_night:
            score = max_weight * 0.90
            reasons.append("Standalone 24/7 ATM kiosk active during night window")
        else:
            score = max_weight * 0.80
    else:  # POS / Merchant
        score = max_weight * (0.30 if is_night else 0.70)

    # 4. Historical hour affinity bonus
    if hist_freq.get(terminal.terminal_id, 0) > 0:
        score = min(max_weight, score + (max_weight * 0.25))
        reasons.append("Historical cash-out affinity in this time window")

    # 5. Low cash status warning
    if cash_status == "LOW_CASH":
        score *= 0.5
        reasons.append("Terminal reported LOW_CASH warning")

    return min(max_weight, score), reasons


def rank_terminals(
    graph: GraphStore,
    account_id: str,
    terminals: List[TerminalNode],
    window_start: Optional[datetime] = None,
    target_withdrawal_amount: Optional[float] = None,
    as_of: Optional[datetime] = None,
) -> List[TerminalScore]:
    """Rank candidate cash-out terminals for `account_id` using dynamic density weights and telemetry."""
    if not terminals:
        return []
    window_start = window_start or utcnow()
    anchor = _anchor_point(graph, account_id, terminals, as_of=as_of)

    freq: Counter = network_terminal_frequency(graph, account_id, degrees=1, as_of=as_of)
    members = {account_id} | graph.get_neighborhood(account_id, degrees=1, as_of=as_of)
    hist_members: Counter = Counter()
    for m in members:
        for t in set(graph.historical_terminal_ids(m, as_of=as_of)):
            hist_members[t] += 1

    meta: Optional[AccountNodeMetadata] = graph.get_account_metadata(account_id)

    # Check if account has AEPS dominant transaction history
    recent_txns = graph.transactions_involving(account_id, window_seconds=86400, direction="both", as_of=window_start)
    aeps_count = sum(1 for t in recent_txns if getattr(t, "payment_channel", "") == "AEPS")
    is_aeps_dominant = (len(recent_txns) > 0 and (aeps_count / len(recent_txns)) >= 0.5)

    # Compute Terminal Density Index (TDI)
    tdi = compute_terminal_density(anchor, terminals, radius_km=5.0) if anchor else 5
    weights = _resolve_dynamic_weights(tdi, account_is_aeps_dominant=is_aeps_dominant)

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
        max_dist = 1.0

    scores: List[TerminalScore] = []
    for t in candidate_terminals:
        c: Dict[str, float] = {}
        reasons_list: List[str] = []

        # 1. History
        hist_score = (weights["history"] * freq.get(t.terminal_id, 0) / max_freq) if max_freq else 0.0
        c["history"] = hist_score
        if freq.get(t.terminal_id, 0) > 0:
            reasons_list.append(f"Account historical hit count ({freq[t.terminal_id]})")

        # 2. Distance
        if anchor is None:
            c["distance"] = weights["distance"] * 0.5
        else:
            d = distances.get(t.terminal_id, 0.0)
            c["distance"] = weights["distance"] * (1.0 - d / max_dist)
            if d < 1.0:
                reasons_list.append(f"Immediate proximity ({d:.2f} km)")
            elif d < 3.0:
                reasons_list.append(f"Nearby corridor ({d:.2f} km)")

        # 3. Time pattern & operational telemetry
        time_score, tel_reasons = _telemetry_and_time_score(t, freq, window_start, max_weight=weights["time_pattern"])
        c["time_pattern"] = time_score
        reasons_list.extend(tel_reasons)

        # 4. Terminal type & liquidity check
        base_type_weight = weights["terminal_type"]
        if t.terminal_type == "AEPS_MICRO_ATM":
            type_score = base_type_weight * 1.0
            # Liquidity check against target withdrawal amount
            daily_limit = getattr(t, "daily_cash_limit", 50000.0)
            if target_withdrawal_amount and target_withdrawal_amount > daily_limit:
                reasons_list.append(f"AEPS CSP agent float limit (₹{daily_limit:,.0f} limit vs ₹{target_withdrawal_amount:,.0f} req)")
            else:
                reasons_list.append("AEPS Micro-ATM / CSP Point")
        elif t.terminal_type == "ATM_KIOSK":
            type_score = base_type_weight * 0.85
            reasons_list.append("24x7 High-Capacity ATM Kiosk")
        else:
            type_score = base_type_weight * 0.40
            reasons_list.append("POS / Retail Terminal")
        c["terminal_type"] = type_score

        # 5. Network association (mule cluster sharing)
        n_assoc = hist_members.get(t.terminal_id, 0)
        c["network_association"] = min(weights["network_association"], n_assoc * (weights["network_association"] / 3.0))
        if n_assoc > 1:
            reasons_list.append(f"Shared across {n_assoc} accounts in syndicate cluster")

        # 6. District relevance
        if meta and meta.district_pincode:
            c["district_relevance"] = weights["district_relevance"] if t.district_pincode == meta.district_pincode else 0.0
            if t.district_pincode == meta.district_pincode:
                reasons_list.append(f"Matches home district PIN ({t.district_pincode})")
        else:
            c["district_relevance"] = weights["district_relevance"] * 0.5

        priority = round(sum(c.values()), 1)
        scores.append(TerminalScore(terminal=t, priority=priority, components=c, reasons=reasons_list))

    scores.sort(key=lambda s: s.priority, reverse=True)
    return scores


def predict_terminal_corridor(
    graph: GraphStore,
    account_id: str,
    ranked_scores: List[TerminalScore],
    window_start: Optional[datetime] = None,
    max_waypoints: int = 3,
) -> Optional[TerminalCorridor]:
    """Predict a prioritized 3-terminal cash-out corridor route linking primary ATM and fallbacks."""
    if not ranked_scores:
        return None

    window_start = window_start or utcnow()
    primary = ranked_scores[0]
    primary_term = primary.terminal
    primary_lat = primary_term.latitude
    primary_lon = primary_term.longitude

    waypoints: List[CorridorWaypoint] = []
    # 1. Add Primary Waypoint (Order 1)
    waypoints.append(
        CorridorWaypoint(
            terminal_id=primary_term.terminal_id,
            order=1,
            terminal_type=primary_term.terminal_type,
            latitude=primary_lat,
            longitude=primary_lon,
            distance_km_from_primary=0.0,
            estimated_transit_minutes=0.0,
            cash_status=getattr(primary_term, "cash_status", "ONLINE_DISPENSING"),
            operating_hours=getattr(primary_term, "operating_hours", "24x7"),
            priority_score=primary.priority,
            reasons=list(primary.reasons),
        )
    )

    # 2. Select sequential fallback waypoints within 3.5 km corridor
    order = 2
    max_radius = 0.0
    for cand in ranked_scores[1:]:
        if order > max_waypoints:
            break
        cand_term = cand.terminal
        dist = _haversine_km(primary_lat, primary_lon, cand_term.latitude, cand_term.longitude)
        
        # Corridor criteria: within 3.5 km and operating/open
        if dist <= 3.5 and getattr(cand_term, "cash_status", "ONLINE_DISPENSING") not in ("CASH_OUT", "OFFLINE"):
            transit_mins = max(1.0, round(dist * 3.0, 1))  # ~20 km/h urban transit velocity
            wp_reasons = list(cand.reasons)
            wp_reasons.append(f"Fallback hop #{order}: {dist:.2f} km (~{transit_mins:.0f}m transit)")
            waypoints.append(
                CorridorWaypoint(
                    terminal_id=cand_term.terminal_id,
                    order=order,
                    terminal_type=cand_term.terminal_type,
                    latitude=cand_term.latitude,
                    longitude=cand_term.longitude,
                    distance_km_from_primary=round(dist, 2),
                    estimated_transit_minutes=transit_mins,
                    cash_status=getattr(cand_term, "cash_status", "ONLINE_DISPENSING"),
                    operating_hours=getattr(cand_term, "operating_hours", "24x7"),
                    priority_score=cand.priority,
                    reasons=wp_reasons,
                )
            )
            max_radius = max(max_radius, dist)
            order += 1

    # If density is low and no nearby fallbacks found, pick next best candidate
    if len(waypoints) < 2 and len(ranked_scores) > 1:
        fallback = ranked_scores[1]
        dist = _haversine_km(primary_lat, primary_lon, fallback.terminal.latitude, fallback.terminal.longitude)
        transit_mins = max(1.0, round(dist * 3.0, 1))
        waypoints.append(
            CorridorWaypoint(
                terminal_id=fallback.terminal.terminal_id,
                order=2,
                terminal_type=fallback.terminal.terminal_type,
                latitude=fallback.terminal.latitude,
                longitude=fallback.terminal.longitude,
                distance_km_from_primary=round(dist, 2),
                estimated_transit_minutes=transit_mins,
                cash_status=getattr(fallback.terminal, "cash_status", "ONLINE_DISPENSING"),
                operating_hours=getattr(fallback.terminal, "operating_hours", "24x7"),
                priority_score=fallback.priority,
                reasons=list(fallback.reasons),
            )
        )
        max_radius = max(max_radius, dist)

    # Calculate combined corridor confidence
    primary_prob = min(1.0, primary.priority / 100.0)
    corridor_conf = min(0.98, round(primary_prob + 0.15 * (1.0 - primary_prob), 2))

    sector_label = primary_term.district or f"PIN {primary_term.district_pincode}" or "Metro Corridor"
    reasons = [
        f"Multi-terminal cash-out corridor encompassing {len(waypoints)} prioritized escape terminals",
        f"Primary egress point: {primary_term.terminal_id} ({primary.priority:.0f}/100 priority)",
        f"Corridor radius: {max_radius:.2f} km across {sector_label}",
    ]

    return TerminalCorridor(
        corridor_id=f"CORR-{account_id}-{primary_term.terminal_id}",
        target_account_id=account_id,
        primary_terminal_id=primary_term.terminal_id,
        waypoints=waypoints,
        corridor_confidence=corridor_conf,
        corridor_radius_km=round(max(0.5, max_radius), 2),
        recommended_patrol_sector=f"Patrol Sector {sector_label}",
        reasons=reasons,
    )