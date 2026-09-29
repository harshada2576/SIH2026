"""tests/test_validation_engine.py — Unit tests and determinism test for validation engine."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "data-generator") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "data-generator"))

from normal_traffic import generate_accounts, generate_terminals, generate_normal_transactions
from patterns import inject_all_scenarios
from pipeline.validation_engine import (
    calculate_bootstrap_ci,
    compile_summary_metrics,
    run_single_seed_validation,
    SingleScenarioResult,
)
from scripts.run_validation import generate_seed_dataset


def test_bootstrap_ci_hand_checkable():
    """Test bootstrap confidence interval with fixed array."""
    data = [1.0, 1.0, 1.0, 0.0, 0.0]
    low, high = calculate_bootstrap_ci(data, num_resamples=100, seed=42)
    assert 0.0 <= low <= high <= 1.0


def test_compile_summary_metrics():
    """Test compilation of metrics on hand-constructed scenario results."""
    e1 = SingleScenarioResult(
        scenario_id="S1",
        difficulty_tier="EASY",
        target_account_id="A1",
        actual_terminal_id="T1",
        actual_latitude=28.60,
        actual_longitude=77.20,
        trigger_timestamp="2026-09-01T10:00:00Z",
        top1_hit_radius=True,
        top3_hit_radius=True,
        top5_hit_radius=True,
        top1_hit_exact=True,
        top3_hit_exact=True,
        top5_hit_exact=True,
        rank1_distance_km=0.5,
        rank1_priority=85.0,
        predicted_terminals=[],
        lead_time_minutes=15.0,
        within_predicted_window=True,
        high_priority_false_positive=False,
        baseline_random_top3_hit=False,
        baseline_history_top3_hit=True,
        baseline_centroid_top3_hit=False,
    )
    res = compile_summary_metrics([e1], seed=42)
    assert res["synthetic"] is True
    assert res["overall"]["top3_radius"] == 100.0
    assert res["overall"]["median_distance_km"] == 0.5


def test_validation_determinism():
    """Assert running validation engine twice on the same seed produces byte-identical results."""
    accounts, terminals, all_txns, scenarios = generate_seed_dataset(seed=42, num_acc=100, num_term=20, num_norm=150)
    run1 = run_single_seed_validation(scenarios, accounts, terminals, all_txns, seed=42)
    run2 = run_single_seed_validation(scenarios, accounts, terminals, all_txns, seed=42)

    json1 = json.dumps(run1, sort_keys=True)
    json2 = json.dumps(run2, sort_keys=True)

    assert json1 == json2
