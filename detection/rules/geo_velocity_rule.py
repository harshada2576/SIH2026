"""Geo-velocity rule: physically-impossible travel between two cash-out
locations for the same account (the "lives in Mumbai, card used in Hyderabad
40 minutes later" case from the mentor review).

This is rule #9. It is intentionally decoupled from the locked 7-field
TransactionEvent/`transactions` Kafka topic (Architecture.md §6.1) — it reads
from GraphStore's separate `terminal_usage` timeline (see
pipeline/graph_store.py: record_terminal_usage / recent_terminal_usages),
which is fed by AEPS/ATM/POS cash-out events carrying a real terminal_id and
lat/long. This keeps the rule fully additive: it never requires changes to
the locked transaction schema that the rest of the team builds against.
"""
from __future__ import annotations

import math
from typing import Optional

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult

EARTH_RADIUS_KM = 6371.0

# Implied speed required to explain two withdrawals -> severity.
# <60 km/h: same city/short drive, not notable.
# 60-250 km/h: plausible train/highway trip.
# 250-600 km/h: only explainable by domestic flight -- unusual for a walk-up
#   cash withdrawal pattern, worth a human look.
# 600+ km/h: exceeds any real transport option for the given gap -> practically
#   impossible, i.e. one of the two withdrawals is very likely not genuine.
SPEED_SEVERITY_BINS = [
    (0, 0.0),
    (60, 0.3),
    (250, 0.7),
    (600, 1.0),
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/long points, in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _speed_severity(speed_kmh: float) -> float:
    sev = 0.0
    for threshold, s in SPEED_SEVERITY_BINS:
        if speed_kmh >= threshold:
            sev = s
        else:
            break
    return sev


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    """Severity from the implied travel speed between the two most recent
    physical cash-out locations for this account.

    Needs at least 2 recorded terminal_usage events; otherwise 0.0 (no signal,
    not "safe" -- just not enough data yet).
    """
    usages = graph.recent_terminal_usages(account_id, limit=2)
    if len(usages) < 2:
        return RuleResult(
            "geo_velocity", 0.0, "fewer than 2 recorded cash-out locations",
            "Geo-velocity: not enough location history to evaluate").clamped()

    a, b = usages[-2], usages[-1]
    if None in (a["latitude"], a["longitude"], b["latitude"], b["longitude"]):
        return RuleResult(
            "geo_velocity", 0.0, "terminal coordinates unavailable",
            "Geo-velocity: terminal location data missing, skipped").clamped()

    distance_km = haversine_km(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
    seconds = max(1.0, (b["timestamp"] - a["timestamp"]).total_seconds())
    hours = seconds / 3600.0
    implied_speed = distance_km / hours if hours > 0 else float("inf")

    severity = _speed_severity(implied_speed)
    measured = (f"{distance_km:.0f} km between {a['terminal_id']} and {b['terminal_id']} "
                f"in {seconds / 60:.0f} min (implied speed {implied_speed:.0f} km/h)")
    if severity >= 1.0:
        evidence = (f"Geo-velocity: IMPOSSIBLE TRAVEL — {a['terminal_id']} to {b['terminal_id']} "
                    f"({distance_km:.0f} km) in {seconds / 60:.0f} minutes, requiring "
                    f"{implied_speed:.0f} km/h — exceeds any plausible transport for this gap")
    elif severity >= 0.7:
        evidence = (f"Geo-velocity: {a['terminal_id']} to {b['terminal_id']} ({distance_km:.0f} km) "
                    f"in {seconds / 60:.0f} minutes only explainable by a flight — unusual for "
                    f"routine cash withdrawal behaviour")
    elif severity >= 0.3:
        evidence = (f"Geo-velocity: {a['terminal_id']} to {b['terminal_id']} ({distance_km:.0f} km) "
                    f"in {seconds / 60:.0f} minutes, a fast but plausible trip")
    else:
        evidence = f"Geo-velocity: consecutive withdrawals consistent with normal local movement"
    return RuleResult("geo_velocity", severity, measured, evidence).clamped()
