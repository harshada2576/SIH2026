"""api/integration_routes.py — Institutional Integration REST Endpoints for CyberShield (SIH26184).

Provides:
- GET /integrations/status: Connector health, roadmap state, simulated flag
- GET /cases/{id}/dispatch-status: Delivery status across institutional connectors
- POST /cases/{id}/dispatch: Execute human-approved institutional dispatch
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request

from pipeline.integration_adapters import InstitutionalIntegrationManager

router = APIRouter(prefix="/integrations", tags=["Integrations"])
manager = InstitutionalIntegrationManager()


@router.get("/status")
async def get_integration_status(role: str = Query("BANK")):
    mode = os.getenv("INTEGRATION_MODE", "simulated").lower()
    return {
        "synthetic": True,
        "simulated": True,
        "role": role,
        "mode": mode,
        "roadmap_state": "Interface Ready / Simulated (Live: Future)",
        "notice": "SIMULATED: no live institutional connection. Future integration layer.",
        "connectors": manager.get_connector_statuses()["connectors"],
    }


@router.get("/cases/{case_id}/dispatch-status")
async def get_case_dispatch_status(case_id: str, role: str = Query("BANK")):
    return {
        "synthetic": True,
        "simulated": True,
        "role": role,
        "case_id": case_id,
        "dispatch_status": {
            "bank_core": "SIMULATED_SENT",
            "lea_police_portal": "SIMULATED_SENT",
            "i4c_ncrp_gateway": "SIMULATED_SENT",
        },
        "connectors": manager.get_connector_statuses()["connectors"],
    }


@router.post("/cases/{case_id}/dispatch")
async def dispatch_case_to_institutions(case_id: str, request: Request, role: str = Query("BANK")):
    try:
        body = await request.json()
    except Exception:
        body = {}

    reason = body.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Human review reason is required prior to institutional dispatch.")

    action = body.get("action", "approve_forward")
    from api.server import ENGINE
    case = ENGINE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    try:
        result = manager.dispatch_case_decision(case, action, role, reason)
        return {
            "synthetic": True,
            "simulated": True,
            "ok": True,
            "dispatch": result,
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
