"""tests/test_phase2_rules.py — unit tests for geo_velocity, identity_cluster,
ml_anomaly, confidence scoring, and the GraphStore methods that back them.

Follows the same helpers/conventions as tests/test_rules.py.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.helpers import acct, aid, graph_with, minutes_ago, now_utc, txn
from detection import confidence
from detection.rules import geo_velocity_rule, identity_cluster_rule, ml_anomaly_rule
from detection.scorer import evaluate_account
from pipeline.graph_store import GraphStore
from shared.schemas import AccountNodeMetadata


# ============================================================================
# GEO-VELOCITY RULE
# ============================================================================

def test_geo_velocity_flags_impossible_travel():
    """Mumbai -> Hyderabad (~620km) in 40 minutes implies ~930 km/h -> severity 1.0."""
    g = GraphStore()
    g.add_account_metadata(acct("A"))
    base = now_utc()
    g.record_terminal_usage(aid("A"), "MUM-1", minutes_ago(45, base), latitude=19.0760, longitude=72.8777)
    g.record_terminal_usage(aid("A"), "HYD-1", minutes_ago(5, base), latitude=17.3850, longitude=78.4867)
    r = geo_velocity_rule.evaluate(g, aid("A"), as_of=base)
    assert r.severity == 1.0
    assert "km/h" in r.measured


def test_geo_velocity_ignores_plausible_local_movement():
    """Two withdrawals 2km apart, 30 minutes apart -> clearly plausible, severity 0."""
    g = GraphStore()
    g.add_account_metadata(acct("A"))
    base = now_utc()
    g.record_terminal_usage(aid("A"), "T1", minutes_ago(30, base), latitude=28.6139, longitude=77.2090)
    g.record_terminal_usage(aid("A"), "T2", minutes_ago(2, base), latitude=28.6229, longitude=77.2100)
    r = geo_velocity_rule.evaluate(g, aid("A"), as_of=base)
    assert r.severity == 0.0


def test_geo_velocity_needs_two_data_points():
    g = GraphStore()
    g.add_account_metadata(acct("A"))
    r = geo_velocity_rule.evaluate(g, aid("A"))
    assert r.severity == 0.0
    assert "not enough" in r.evidence.lower()


# ============================================================================
# IDENTITY-CLUSTER RULE
# ============================================================================

def test_identity_cluster_flags_large_shared_kyc_ring():
    g = GraphStore()
    for i in range(12):
        g.add_account_metadata(AccountNodeMetadata(
            account_id=aid(f"M{i:02d}"), account_tier="mule_l1",
            kyc_identity_id="KYC-SHARED-1"))
    r = identity_cluster_rule.evaluate(g, aid("M00"))
    assert r.severity == 1.0
    assert "mule ring" in r.evidence.lower()


def test_identity_cluster_zero_when_no_shared_identity():
    g = GraphStore()
    g.add_account_metadata(AccountNodeMetadata(account_id=aid("A"), kyc_identity_id=None))
    r = identity_cluster_rule.evaluate(g, aid("A"))
    assert r.severity == 0.0


def test_identity_cluster_is_independent_of_device_fingerprint():
    """Same KYC identity, but every account uses a DIFFERENT device — should
    still fire, proving this is a distinct signal from device_fingerprint_rule."""
    g = GraphStore()
    base = now_utc()
    accounts = [f"M{i:02d}" for i in range(10)]
    for i, a in enumerate(accounts):
        g.add_account_metadata(AccountNodeMetadata(
            account_id=aid(a), kyc_identity_id="KYC-SHARED-2"))
    # give each a distinct device via a dummy transaction
    for i, a in enumerate(accounts):
        g.add_transaction(txn(f"t{i}", a, "ACC-SINK", 1000, minutes_ago(5, base), device=f"DEV-UNIQUE-{i}"))
    r = identity_cluster_rule.evaluate(g, aid(accounts[0]))
    assert r.severity == 1.0


# ============================================================================
# ML-ANOMALY RULE (hybrid rule + ML layer)
# ============================================================================

def test_ml_anomaly_degrades_gracefully_on_small_population():
    """With <12 accounts it must fall back to the z-score path and never crash."""
    g = GraphStore()
    base = now_utc()
    g.add_account_metadata(acct("A"))
    g.add_account_metadata(acct("B"))
    g.add_transaction(txn("t1", "A", "B", 5000, minutes_ago(5, base)))
    r = ml_anomaly_rule.evaluate(g, aid("A"), as_of=base)
    assert 0.0 <= r.severity <= 1.0
    assert "fallback" in r.measured.lower() or "population" in r.measured.lower()


def test_ml_anomaly_flags_extreme_outlier_against_normal_population():
    g = GraphStore()
    base = now_utc()
    normal_accounts = [f"N{i:02d}" for i in range(20)]
    for a in normal_accounts:
        g.add_account_metadata(acct(a))
    for i, a in enumerate(normal_accounts):
        g.add_transaction(txn(f"norm{i}", a, "ACC-SINK", 2000, minutes_ago(200, base)))

    g.add_account_metadata(acct("OUTLIER"))
    # 20 distinct fast senders into OUTLIER within the 5-minute fan window -> extreme fan-in
    for i in range(20):
        g.add_transaction(txn(f"out{i}", f"S{i:02d}", "OUTLIER", 900000, minutes_ago(1, base)))

    r = ml_anomaly_rule.evaluate(g, aid("OUTLIER"), as_of=base)
    assert r.severity > 0.5


# ============================================================================
# CONFIDENCE SCORING
# ============================================================================

def test_confidence_higher_with_more_agreeing_rules():
    g = GraphStore()
    base = now_utc()
    # Weak case: single-sender, no other signals
    g.add_account_metadata(acct("WEAK"))
    g.add_transaction(txn("w1", "X", "WEAK", 1000, minutes_ago(5, base)))
    ev_weak = evaluate_account(g, aid("WEAK"), as_of=base)
    conf_weak = confidence.compute_confidence(ev_weak)

    # Strong case: many agreeing rules (fan-in + fast pass-through + new account)
    g2 = GraphStore()
    g2.add_account_metadata(AccountNodeMetadata(account_id=aid("STRONG"), account_age_days=1))
    for i in range(8):
        g2.add_transaction(txn(f"s{i}", f"SRC{i}", "STRONG", 20000, minutes_ago(5, base)))
    g2.add_transaction(txn("out1", "STRONG", "SINK", 150000, minutes_ago(5, base) + timedelta(seconds=30)))
    ev_strong = evaluate_account(g2, aid("STRONG"), as_of=base)
    conf_strong = confidence.compute_confidence(ev_strong)

    assert conf_strong > conf_weak


def test_confidence_label_thresholds():
    assert confidence.confidence_label(0.9) == "HIGH"
    assert confidence.confidence_label(0.5) == "MEDIUM"
    assert confidence.confidence_label(0.1) == "LOW"
