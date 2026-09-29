"""FastAPI & WebSocket REST backend for CyberShield Native Android App (SIH26184).

Provides:
- Dynamic LAN discovery (mDNS / Zeroconf & UDP broadcast)
- Real-time WebSocket live event delivery to 3-5 concurrent mobile devices
- High-velocity transaction processing & Explainable AI alert dispatch
- Reverse intervention actions (Bank Hold, Police Forward, Dismiss, Release)
"""
from __future__ import annotations

import asyncio
import json
import logging
import socket
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.discovery import DiscoveryService, get_primary_lan_ip
from api.engine import CaseEngine
from detection import scorer
from detection.auto_intervention import decide as decide_intervention
from shared.schemas import AccountNodeMetadata, TransactionEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("cybershield_api")

ENGINE = CaseEngine()
discovery_service: Optional[DiscoveryService] = None


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Client Manager (Broadcasts live events to 3-5+ mobile phones)
# ─────────────────────────────────────────────────────────────────────────────
class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        log.info(f"[WS] Mobile client connected. Total connected devices: {len(self.active_connections)}")
        # Send initial handshake state
        await websocket.send_text(json.dumps({
            "type": "HANDSHAKE_ACK",
            "server": "CyberShield SIH26184",
            "version": "1.0.0",
            "lan_ip": get_primary_lan_ip(),
            "active_cases": len(ENGINE.cases),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        log.info(f"[WS] Mobile client disconnected. Remaining devices: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: Any) -> None:
        payload = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, default=str)
        
        dead_connections = set()
        async with self._lock:
            connections = list(self.active_connections)

        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception as e:
                log.warning(f"[WS] Send failed for a client: {e}")
                dead_connections.add(ws)

        if dead_connections:
            async with self._lock:
                for ws in dead_connections:
                    self.active_connections.discard(ws)


ws_manager = WebSocketManager()


def sync_broadcast(event_type: str, data: Any) -> None:
    """Helper to dispatch WebSocket broadcasts from synchronous engine callbacks."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ws_manager.broadcast(event_type, data))
    except RuntimeError:
        # No running event loop in thread
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan Management (Auto-starts discovery advertising on boot)
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global discovery_service
    port = getattr(app.state, "port", 5003)
    lan_ip = get_primary_lan_ip()
    log.info(f"==================================================================")
    log.info(f"🛡️  CyberShield SIH26184 Detection & Live Dispatch API")
    log.info(f"LAN Endpoint: http://{lan_ip}:{port}")
    log.info(f"WebSocket:    ws://{lan_ip}:{port}/ws")
    log.info(f"Loaded {len(ENGINE.cases)} active investigation cases from detection engine")
    log.info(f"==================================================================")

    discovery_service = DiscoveryService(port=port, service_name="CyberShield-Backend")
    discovery_service.start()

    yield

    if discovery_service:
        discovery_service.stop()


from api.validation_routes import router as validation_router
from api.integration_routes import router as integration_router

app = FastAPI(
    title="CyberShield SIH26184 Backend",
    description="Predictive Cash Egress Interception Platform Backend & Real-time Live Alert Hub",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(validation_router)
app.include_router(integration_router)


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Real-Time Alert Channel
# ─────────────────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep receiving client pings or client action requests
            msg_text = await websocket.receive_text()
            try:
                req = json.loads(msg_text)
                action = req.get("action")
                if action == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG", "time": datetime.now(timezone.utc).isoformat()}))
                elif action == "GET_CASES":
                    role = req.get("role", "BANK")
                    await websocket.send_text(json.dumps({
                        "type": "CASES_SNAPSHOT",
                        "data": ENGINE.list_cases(role)
                    }, default=str))
            except Exception:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        log.debug(f"[WS] Connection ended: {e}")
        await ws_manager.disconnect(websocket)


# ─────────────────────────────────────────────────────────────────────────────
# REST Endpoints for CyberShield Native Android App
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "ok": True,
        "status": "ONLINE",
        "service": "CyberShield Backend",
        "project": "SIH26184",
        "version": "1.0.0",
        "lan_ip": get_primary_lan_ip(),
        "cases": len(ENGINE.cases),
        "terminals": len(ENGINE.terminals),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/cases")
async def list_cases(role: str = Query("BANK", description="Role filter: BANK or POLICE")):
    cases = ENGINE.list_cases(role)
    return {"cases": cases}


@app.get("/cases/{ncrp_id}")
async def get_case(ncrp_id: str):
    case = ENGINE.get(ncrp_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/cases/{ncrp_id}/{action}")
async def act_on_case(ncrp_id: str, action: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    if action == "notify":
        case = ENGINE.get(ncrp_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case {ncrp_id} not found")
        from pipeline.notification_service import NotificationEvent
        ev_type = body.get("event_type", "HIGH_RISK_CASE")
        results = ENGINE.notification_service.notify(NotificationEvent(
            event_type=ev_type,
            case_id=ncrp_id,
            account_id=case.get("flaggedAccountId", ""),
            amount=float(body.get("amount") or case.get("suspiciousExposure") or 100000.0),
            terminal_id=case.get("targetTerminal", {}).get("id"),
            terminal_location=case.get("targetTerminal", {}).get("address"),
            status=case.get("status"),
            details=body,
        ))
        case["notificationStatus"] = ENGINE.notification_service.get_case_notification_summary(ncrp_id).get("channels", {})
        case["notifications"] = ENGINE.notification_service.get_case_notification_summary(ncrp_id).get("items", [])
        
        await ws_manager.broadcast("CASE_UPDATED", {
            "case": case,
            "action": "notify",
            "ncrpId": ncrp_id,
            "audit": ENGINE.audit[0] if ENGINE.audit else None
        })
        
        return {
            "ok": True,
            "case_id": ncrp_id,
            "dispatched_count": len(results),
            "notifications": [r.to_dict() for r in results],
        }

    officer = body.get("officer") or "Duty officer"
    updated_case = ENGINE.act(ncrp_id, action, officer)
    if updated_case is None:
        raise HTTPException(status_code=404, detail=f"Case {ncrp_id} not found")

    # Broadcast updated case state to all connected phones immediately
    await ws_manager.broadcast("CASE_UPDATED", {
        "case": updated_case,
        "action": action,
        "officer": officer,
        "ncrpId": ncrp_id,
        "audit": ENGINE.audit[0] if ENGINE.audit else None
    })

    return updated_case


@app.get("/cases/{case_id}/notifications")
async def get_case_notifications(case_id: str):
    case = ENGINE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    notifs = ENGINE.notification_service.get_case_notifications(case_id)
    summary = ENGINE.notification_service.get_case_notification_summary(case_id)
    return {
        "case_id": case_id,
        "summary": summary,
        "notifications": notifs,
    }


@app.get("/terminals")
async def list_terminals():
    return {"terminals": ENGINE.terminal_markers()}


@app.get("/audit")
async def list_audit():
    return {"audit": ENGINE.audit}


@app.get("/heatmap")
async def get_heatmap(
    event_type: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    case_id: Optional[str] = Query(None),
    aggregate: bool = Query(True)
):
    return ENGINE.get_heatmap_points(
        case_id=case_id,
        event_type=event_type,
        city=city,
        start_time=start_time,
        end_time=end_time,
        aggregate=aggregate
    )


@app.get("/cases/{case_id}/heatmap")
async def get_case_heatmap(
    case_id: str,
    event_type: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    aggregate: bool = Query(True)
):
    case = ENGINE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return ENGINE.get_heatmap_points(
        case_id=case_id,
        event_type=event_type,
        city=city,
        start_time=start_time,
        end_time=end_time,
        aggregate=aggregate
    )


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic Live Demo Trigger Flow
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/demo/trigger_fraud")
async def trigger_live_fraud_alert():
    """Generates a synthetic suspicious mule transaction into GraphStore, runs 
    explainable heuristic detection rules, creates a high-priority risk alert, 
    and broadcasts it over WebSockets to all connected phones live."""
    base = datetime.now(timezone.utc)
    victim = f"ACC-VIC-LIVE-{base.strftime('%M%S')}"
    target = f"ACC-MULE-LIVE-{base.strftime('%M%S')}"
    
    ENGINE.graph.add_account_metadata(AccountNodeMetadata(
        account_id=victim, account_tier="victim", account_age_days=620
    ))
    ENGINE.graph.add_account_metadata(AccountNodeMetadata(
        account_id=target, account_tier="mule_l1", account_age_days=3,
        historical_terminal_ids=["ATM-HDFC-BKC-011"], district_pincode="400051"
    ))

    # Rapid fan-in burst
    for i in range(5):
        txn = TransactionEvent(
            transaction_id=f"TXN-LIVE-{base.strftime('%H%M%S')}-{i+1}",
            source_account_id=victim if i == 0 else f"ACC-FEED-LIV{i}",
            target_account_id=target,
            amount_inr=25000.0,
            timestamp=base - timedelta(seconds=(5 - i) * 15),
            payment_channel="UPI",
            device_fingerprint="DEV-LIVE-FRAUD-RING"
        )
        if i > 0:
            ENGINE.graph.add_account_metadata(AccountNodeMetadata(account_id=f"ACC-FEED-LIV{i}", account_tier="mule_l2", account_age_days=2))
        ENGINE.graph.add_transaction(txn)

    # Run detection rules
    ev = scorer.evaluate_account(ENGINE.graph, target, as_of=base)
    term_nodes = scorer.load_terminals()
    alert = scorer.analyze(ENGINE.graph, target, terminals=term_nodes, as_of=base, notify_threshold=1)
    
    if alert:
        decision = decide_intervention(alert, ev.band)
        new_case = ENGINE._to_case(target, ev, alert, decision)
        new_case["demoTag"] = "live-stream"
        new_case["summary"] = f"CRITICAL: Live UPI fan-in detected on {target}. ₹1,25,000 ingress in 2 mins across shared device fingerprint. Predicted egress {new_case['targetTerminal']['id']}."
        ENGINE.cases[new_case["ncrpId"]] = new_case
        ENGINE._log(new_case["ncrpId"], "Live detection alert generated from transaction stream", new_case["status"], "Detection Engine")

        # Broadcast live alert to all connected Android devices
        await ws_manager.broadcast("NEW_ALERT", {
            "case": new_case,
            "message": "🚨 New Critical Risk Alert Intercepted!",
            "audit": ENGINE.audit[0] if ENGINE.audit else None
        })

        return {
            "status": "ALERT_DISPATCHED",
            "ncrpId": new_case["ncrpId"],
            "flaggedAccount": target,
            "riskScore": ev.score,
            "band": ev.band,
            "case": new_case
        }
    
    return {"status": "NO_ALERT_GENERATED"}


def run(port: int = 5003) -> None:
    import uvicorn
    app.state.port = port
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 5003
    run(port_arg)
