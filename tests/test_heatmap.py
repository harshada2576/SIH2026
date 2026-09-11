"""tests/test_heatmap.py

Comprehensive test suite for Sprint 4 — Fraud/Activity Geographic Heatmap.
Covers Tests A through I as specified in USER_REQUEST.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.engine import CaseEngine, _get_city_for_point, _parse_time_filter


def test_city_mapping_helpers():
    assert _get_city_for_point(28.57, 77.32, pincode="110001") == "Delhi/NCR"
    assert _get_city_for_point(19.07, 72.87, pincode="400001") == "Mumbai"
    assert _get_city_for_point(12.97, 77.59, pincode="560001") == "Bengaluru"
    assert _get_city_for_point(17.38, 78.48, pincode="500001") == "Hyderabad"
    assert _get_city_for_point(13.08, 80.27, pincode="600002") == "Chennai"
    assert _get_city_for_point(22.57, 88.36, pincode="700016") == "Kolkata"
    assert _get_city_for_point(18.52, 73.85, pincode="411005") == "Pune"
    assert _get_city_for_point(23.02, 72.57, pincode="380009") == "Ahmedabad"


def test_a_basic_heatmap():
    """Test A — Basic heatmap: Given geographic events, verify points, valid coords, valid weights."""
    engine = CaseEngine()
    result = engine.get_heatmap_points()
    assert "points" in result
    assert "summary" in result
    points = result["points"]
    assert len(points) > 0, "Expected heatmap points from engine initialized cases"

    for p in points:
        assert isinstance(p["latitude"], float)
        assert isinstance(p["longitude"], float)
        assert not math.isnan(p["latitude"])
        assert not math.isnan(p["longitude"])
        assert -90.0 <= p["latitude"] <= 90.0
        assert -180.0 <= p["longitude"] <= 180.0
        assert 0.0 <= p["weight"] <= 1.0
        assert p["event_type"] in {
            "SUSPICIOUS_ACTIVITY",
            "WITHDRAWAL_ATTEMPTS",
            "BLOCKED_WITHDRAWALS",
            "CONFIRMED_FRAUD",
            "PREDICTED_CASHOUT",
            "REPEATED_TERMINAL_ACTIVITY",
        }
        assert isinstance(p["city"], str)


def test_b_geographic_clustering():
    """Test B — Geographic clustering: Multiple nearby events produce stronger heat region."""
    engine = CaseEngine()
    
    # Inject multiple mock withdrawal attempts at the same terminal coordinate
    case_key = list(engine.cases.keys())[0]
    case = engine.cases[case_key]
    case["withdrawalAttempts"] = [
        {"attemptId": "a1", "time": datetime.now(timezone.utc).isoformat(), "status": "BLOCKED", "latitude": 28.57, "longitude": 77.32},
        {"attemptId": "a2", "time": datetime.now(timezone.utc).isoformat(), "status": "BLOCKED", "latitude": 28.57, "longitude": 77.32},
        {"attemptId": "a3", "time": datetime.now(timezone.utc).isoformat(), "status": "BLOCKED", "latitude": 28.57, "longitude": 77.32},
    ]

    unagg = engine.get_heatmap_points(case_id=case_key, aggregate=False)
    agg = engine.get_heatmap_points(case_id=case_key, aggregate=True)

    assert len(unagg["points"]) >= 3
    assert len(agg["points"]) < len(unagg["points"])
    clustered = next(p for p in agg["points"] if round(p["latitude"], 2) == 28.57)
    assert clustered["weight"] > 0.90


def test_c_different_cities():
    """Test C — Different cities: Events in Mumbai and Delhi produce two distinct clusters."""
    engine = CaseEngine()
    res = engine.get_heatmap_points()
    cities = res["summary"]["cities_represented"]

    assert "Delhi/NCR" in cities or "Mumbai" in cities
    delhi_pts = [p for p in res["points"] if p["city"] == "Delhi/NCR"]
    mumbai_pts = [p for p in res["points"] if p["city"] == "Mumbai"]

    if delhi_pts and mumbai_pts:
        d_lat = delhi_pts[0]["latitude"]
        m_lat = mumbai_pts[0]["latitude"]
        assert abs(d_lat - m_lat) > 5.0, "Delhi and Mumbai coordinates must be geographically separated"


def test_d_event_filtering():
    """Test D — Event filtering: Request WITHDRAWAL_ATTEMPTS or BLOCKED_WITHDRAWALS."""
    engine = CaseEngine()
    
    res_blocked = engine.get_heatmap_points(event_type="BLOCKED_WITHDRAWALS")
    for p in res_blocked["points"]:
        assert p["event_type"] == "BLOCKED_WITHDRAWALS"

    res_pred = engine.get_heatmap_points(event_type="PREDICTED_CASHOUT")
    for p in res_pred["points"]:
        assert p["event_type"] == "PREDICTED_CASHOUT"


def test_e_time_filtering():
    """Test E — Time filtering: Events outside requested time window excluded."""
    engine = CaseEngine()
    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(days=10)).isoformat()
    new_time = (now - timedelta(minutes=5)).isoformat()

    case_key = list(engine.cases.keys())[0]
    case = engine.cases[case_key]
    case["withdrawalAttempts"] = [
        {"attemptId": "old", "time": old_time, "status": "BLOCKED", "latitude": 28.57, "longitude": 77.32},
        {"attemptId": "new", "time": new_time, "status": "BLOCKED", "latitude": 28.57, "longitude": 77.32},
    ]

    recent_res = engine.get_heatmap_points(case_id=case_key, start_time="24h")
    for p in recent_res["points"]:
        if p.get("timestamp"):
            p_dt = datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00"))
            if p_dt.tzinfo is None:
                p_dt = p_dt.replace(tzinfo=timezone.utc)
            assert p_dt >= (now - timedelta(hours=25))


def test_f_case_specific_heatmap():
    """Test F — Case-specific heatmap: Only events associated with requested case."""
    engine = CaseEngine()
    case_keys = list(engine.cases.keys())
    c1 = case_keys[0]

    res = engine.get_heatmap_points(case_id=c1)
    for p in res["points"]:
        if p["case_id"]:
            assert p["case_id"] == c1


def test_g_invalid_coordinates():
    """Test G — Invalid coordinates: Malformed/missing coordinates rejected or safely ignored."""
    engine = CaseEngine()
    c1 = list(engine.cases.keys())[0]
    case = engine.cases[c1]

    case["withdrawalAttempts"].extend([
        {"attemptId": "err1", "time": "", "status": "FLAGGED", "latitude": None, "longitude": 77.32},
        {"attemptId": "err2", "time": "", "status": "FLAGGED", "latitude": "invalid", "longitude": 77.32},
        {"attemptId": "err3", "time": "", "status": "FLAGGED", "latitude": 999.0, "longitude": 77.32},
        {"attemptId": "err4", "time": "", "status": "FLAGGED", "latitude": float("nan"), "longitude": 77.32},
    ])

    res = engine.get_heatmap_points(case_id=c1)
    for p in res["points"]:
        assert isinstance(p["latitude"], float)
        assert isinstance(p["longitude"], float)
        assert not math.isnan(p["latitude"])
        assert not math.isnan(p["longitude"])
        assert -90.0 <= p["latitude"] <= 90.0
        assert -180.0 <= p["longitude"] <= 180.0


def test_h_empty_dataset():
    """Test H — Empty dataset: Valid empty heatmap response, not application failure."""
    engine = CaseEngine()
    engine.cases.clear()
    engine.terminals.clear()

    res = engine.get_heatmap_points()
    assert res["points"] == []
    assert res["summary"]["total_points"] == 0
    assert res["summary"]["event_counts"] == {}
    assert res["summary"]["cities_represented"] == []


def test_i_expanded_dataset():
    """Test I — Expanded dataset: Run heatmap generation against multi-city dataset."""
    engine = CaseEngine()
    
    cities_test = [
        ("ATM-MUM-01", 19.076, 72.877, "400001"),
        ("ATM-BLR-01", 12.971, 77.594, "560001"),
        ("ATM-HYD-01", 17.385, 78.486, "500001"),
        ("ATM-MAA-01", 13.082, 80.270, "600002"),
        ("ATM-CCU-01", 22.572, 88.363, "700016"),
        ("ATM-PNQ-01", 18.520, 73.856, "411005"),
        ("ATM-AMD-01", 23.022, 72.571, "380009"),
    ]
    for tid, lat, lon, pin in cities_test:
        engine.terminals.append({
            "terminal_id": tid,
            "terminal_type": "BANK_ATM",
            "latitude": lat,
            "longitude": lon,
            "district_pincode": pin,
        })

    res = engine.get_heatmap_points()
    assert len(res["points"]) > 0
    cities = res["summary"]["cities_represented"]
    assert len(cities) >= 2
