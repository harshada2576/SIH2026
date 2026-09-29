"""api/validation_routes.py — Validation API endpoints for CyberShield (SIH26184).

Provides:
- POST /validation/run: Run benchmark validation across seeds
- GET /validation/metrics: Get latest summary metrics
- GET /validation/cases/{id}: Get detailed prediction vs actual withdrawal comparison for a case
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "data" / "output" / "validation_report.json"

router = APIRouter(prefix="/validation", tags=["Validation"])


def _load_report() -> Dict[str, Any]:
    if not REPORT_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Validation report not found. Trigger POST /validation/run first.",
        )
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/metrics")
async def get_validation_metrics(role: str = Query("BANK")):
    report = _load_report()
    return {
        "synthetic": True,
        "role": role,
        "aggregate_metrics": report.get("aggregate_metrics"),
        "baselines_mean_top3_pct": report.get("baselines_mean_top3_pct"),
        "lift_percent": report.get("lift_percent"),
        "pre_registered_verdict": report.get("pre_registered_verdict"),
        "score_reliability_table": report.get("seed_runs", [{}])[0].get("score_reliability_table", []),
    }


@router.get("/cases/{case_id}")
async def get_case_validation_comparison(case_id: str, role: str = Query("BANK")):
    report = _load_report()
    seed_runs = report.get("seed_runs", [])
    if not seed_runs:
        raise HTTPException(status_code=404, detail="No scenario evaluation data available")

    # Search first seed run for matching case/scenario
    evals = seed_runs[0].get("case_details", [])
    match = next((e for e in evals if e.get("scenario_id") == case_id or e.get("target_account_id") == case_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Validation case {case_id} not found")

    return {
        "synthetic": True,
        "role": role,
        "validation_case": match,
    }


@router.post("/run")
async def run_validation_benchmark(
    seeds: Optional[str] = Query("42,43,44,45,46"),
    role: str = Query("BANK"),
):
    from scripts.run_validation import main as run_benchmark_script

    seed_list = [int(s.strip()) for s in seeds.split(",") if s.strip().isdigit()]
    sys_argv_backup = list(sys.argv)
    try:
        sys.argv = ["run_validation.py", "--seeds"] + [str(s) for s in seed_list]
        run_benchmark_script()
    finally:
        sys.argv = sys_argv_backup

    report = _load_report()
    return {
        "synthetic": True,
        "role": role,
        "status": "VALIDATION_COMPLETED",
        "metrics": report.get("aggregate_metrics"),
        "verdict": report.get("pre_registered_verdict"),
    }
