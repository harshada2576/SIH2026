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
from api.pubsub import GLOBAL_EVENT_BUS
from api.security import verify_intervention_security
from export.evidentiary_dossier import generate_evidentiary_dossier
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
        GLOBAL_EVENT_BUS.subscribe(self.handle_cluster_event)

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

    async def handle_cluster_event(self, event: Dict[str, Any]) -> None:
        """Internal dispatch from Redis/async PubSub event bus to local mobile sockets."""
        payload = json.dumps(event, default=str)
        dead = set()
        async with self._lock:
            conns = list(self.active_connections)
        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self.active_connections.discard(ws)

    async def broadcast(self, event_type: str, data: Any, publish_to_cluster: bool = True) -> None:
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if publish_to_cluster:
            await GLOBAL_EVENT_BUS.publish(event)
        else:
            await self.handle_cluster_event(event)


MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None
kafka_consumer_running = False
kafka_thread: Optional[threading.Thread] = None

ws_manager = WebSocketManager()


def sync_broadcast(event_type: str, data: Any) -> None:
    """Helper to dispatch WebSocket broadcasts from synchronous engine or worker threads."""
    global MAIN_LOOP
    try:
        if MAIN_LOOP is not None and MAIN_LOOP.is_running():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(event_type, data), MAIN_LOOP)
        else:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_manager.broadcast(event_type, data))
    except Exception as e:
        log.debug(f"[WS] Broadcast notice: {e}")


def _run_kafka_background_consumer() -> None:
    """Background daemon thread listening on Kafka 'transactions' topic and feeding CaseEngine."""
    global kafka_consumer_running
    try:
        from shared.kafka_utils import (
            KAFKA_BOOTSTRAP_SERVERS,
            TRANSACTIONS_TOPIC,
            get_kafka_consumer,
            safe_json_deserializer,
        )
        log.info(f"[Kafka] Connecting background live consumer to {KAFKA_BOOTSTRAP_SERVERS} on topic '{TRANSACTIONS_TOPIC}'...")
        consumer = get_kafka_consumer(
            TRANSACTIONS_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=safe_json_deserializer,
            auto_offset_reset="latest",
            group_id="cybershield-backend-live-consumer",
            consumer_timeout_ms=2000,
        )
        kafka_consumer_running = True
        log.info(f"[Kafka] Connected! Live stream ingestion active on topic '{TRANSACTIONS_TOPIC}'.")
        while kafka_consumer_running:
            try:
                for msg in consumer:
                    if not kafka_consumer_running:
                        break
                    tx_dict = msg.value
                    if tx_dict and isinstance(tx_dict, dict):
                        ENGINE.process_transaction(tx_dict)
            except Exception as e:
                if kafka_consumer_running:
                    log.debug(f"[Kafka] Consumer poll cycle notice: {e}")
                    import time
                    time.sleep(1)
    except Exception as e:
        log.info(f"[Kafka] Local broker not running or unreachable ({e}). Direct HTTP transaction ingestion is active.")


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan Management (Auto-starts discovery advertising & Kafka consumer on boot)
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global MAIN_LOOP, discovery_service, kafka_thread, kafka_consumer_running
    MAIN_LOOP = asyncio.get_running_loop()
    port = getattr(app.state, "port", 5003)
    lan_ip = get_primary_lan_ip()
    log.info(f"==================================================================")
    log.info(f"🛡️  CyberShield SIH26184 Detection & Live Dispatch API")
    log.info(f"LAN Endpoint: http://{lan_ip}:{port}")
    log.info(f"WebSocket:    ws://{lan_ip}:{port}/ws")
    log.info(f"Loaded {len(ENGINE.cases)} active investigation cases from detection engine")
    log.info(f"==================================================================")

    await GLOBAL_EVENT_BUS.start()

    discovery_service = DiscoveryService(port=port, service_name="CyberShield-Backend")
    discovery_service.start()

    # Launch background Kafka live consumer thread
    import threading
    kafka_thread = threading.Thread(target=_run_kafka_background_consumer, name="KafkaConsumerDaemon", daemon=True)
    kafka_thread.start()

    yield

    kafka_consumer_running = False
    if discovery_service:
        discovery_service.stop()
    await GLOBAL_EVENT_BUS.stop()


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


@app.post("/transactions")
async def ingest_transactions(request: Request):
    """Ingests live transaction(s) into the detection pipeline, updates graph,
    and broadcasts NEW_ALERT over WebSockets if high risk is detected."""
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    if isinstance(payload, list):
        tx_list = payload
    elif isinstance(payload, dict) and "transactions" in payload:
        tx_list = payload["transactions"]
        if "accounts" in payload:
            for acc_raw in payload["accounts"]:
                try:
                    meta = AccountNodeMetadata.from_dict(acc_raw) if not isinstance(acc_raw, AccountNodeMetadata) else acc_raw
                    ENGINE.graph.add_account_metadata(meta)
                except Exception as e:
                    log.debug(f"Metadata registration notice: {e}")
    elif isinstance(payload, dict):
        tx_list = [payload]
    else:
        raise HTTPException(status_code=400, detail="Expected transaction object or list")

    created_cases = []
    for raw in tx_list:
        try:
            case = ENGINE.process_transaction(raw)
            if case:
                created_cases.append(case)
        except Exception as e:
            log.warning(f"Error processing transaction {raw.get('transaction_id')}: {e}")

    return {
        "ok": True,
        "processed": len(tx_list),
        "alerts_generated": len(created_cases),
        "cases": created_cases,
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

    # Security: Verify request signature, timestamp window, nonce replay, and ABAC role
    verify_intervention_security(
        payload={"case_id": ncrp_id, "action": action, **body},
        signature=request.headers.get("x-signature") or request.headers.get("X-Signature"),
        timestamp=request.headers.get("x-timestamp") or request.headers.get("X-Timestamp"),
        nonce=request.headers.get("x-nonce") or request.headers.get("X-Nonce"),
        officer_id=request.headers.get("x-officer-id") or request.headers.get("X-Officer-ID"),
        officer_role=request.headers.get("x-officer-role") or request.headers.get("X-Officer-Role"),
        enforce_strict=False,
    )
    
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


@app.get("/cases/{case_id}/dossier")
async def get_case_evidentiary_dossier(case_id: str, officer_id: str = Query("OFFICER-I4C-CYBERSHIELD")):
    """Export Section 63 BSA / 65B IEA Compliant Electronic Evidence Dossier."""
    case = ENGINE.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    dossier = generate_evidentiary_dossier(case, nodal_officer_id=officer_id)
    return dossier.to_dict()


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
