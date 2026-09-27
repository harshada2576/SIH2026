"""Build live investigation cases from CSV + detection (no Android-side scoring)."""
from __future__ import annotations

import ast
import csv
import logging
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

log = logging.getLogger("case_engine")

from audit.blockchain_lite import AuditLedger
from detection import scorer
from detection.auto_intervention import decide as decide_intervention
from pipeline.graph_store import GraphStore
from pipeline.notification_service import NotificationEvent, NotificationEventType, NotificationService
from scripts.demo_phase2 import (
    build_critical_saturation_case,
    build_geo_velocity_scenario,
    build_mule_identity_ring,
)
from shared.persistence import Store
from shared.schemas import AccountNodeMetadata, TransactionEvent

PLAIN = {
    "velocity": ("Money moved out unusually fast", "Funds left this account much faster than a normal customer would move them."),
    "fan_in": ("Several accounts feeding one account", "Many unrelated accounts sent money into the same collector in a short window."),
    "fan_out": ("Money split out to many accounts", "This account rapidly sent funds onward to several destinations."),
    "layering": ("Money passed through several accounts quickly", "Hops were added to hide where the money started."),
    "amount_movement": ("Almost all incoming money was forwarded", "Very little was kept or spent in a normal pattern."),
    "account_age": ("Account is only days old", "Newly opened accounts are a common mule pattern."),
    "device_fingerprint": ("Same device used across accounts", "One phone or device is linked to accounts that should be unrelated."),
    "terminal_affinity": ("Close to a known cash-out spot", "Historical withdrawals point at this ATM or nearby agents."),
    "geo_velocity": ("Impossible travel between two locations", "The same card/account was used in two cities faster than anyone can travel."),
    "identity_cluster": ("Many accounts opened on one identity", "A cluster of accounts share one KYC identity — typical mule-ring behaviour."),
    "ml_anomaly": ("Unusual behaviour for this account", "Current activity does not match this account's normal pattern."),
    "smurfing_subgraph": ("Structured micro-smurfing split across accounts", "Funds were deliberately split into sub-threshold chunks across intermediate accounts to evade velocity limits."),
}

PIN_LABEL = {
    "110001": "New Delhi",
    "110016": "South Delhi",
    "201301": "Noida",
    "122001": "Gurugram",
    "400001": "South Mumbai",
    "400051": "Bandra BKC, Mumbai",
    "400053": "Andheri, Mumbai",
    "400703": "Navi Mumbai",
    "560001": "Central Bengaluru",
    "560034": "Koramangala, Bengaluru",
    "560066": "Whitefield, Bengaluru",
    "560100": "Electronic City, Bengaluru",
    "500081": "Hitec City, Hyderabad",
    "500034": "Banjara Hills, Hyderabad",
    "500003": "Secunderabad",
    "500002": "Old City Hyderabad",
    "600002": "Anna Salai, Chennai",
    "600113": "OMR Taramani, Chennai",
    "600017": "T-Nagar, Chennai",
    "600032": "Guindy, Chennai",
    "700016": "Park Street, Kolkata",
    "700091": "Salt Lake, Kolkata",
    "700156": "New Town Kolkata",
    "711101": "Howrah, Kolkata",
    "411005": "Shivaji Nagar, Pune",
    "411057": "Hinjewadi, Pune",
    "411028": "Magarpatta, Pune",
    "411038": "Kothrud, Pune",
    "380009": "Navrangpura, Ahmedabad",
    "380054": "SG Highway, Ahmedabad",
    "380008": "Maninagar, Ahmedabad",
    "382010": "Gandhinagar",
    "302001": "MI Road, Jaipur",
    "302017": "Malviya Nagar, Jaipur",
    "302021": "Vaishali Nagar, Jaipur",
    "226001": "Hazratganj, Lucknow",
    "226010": "Gomti Nagar, Lucknow",
    "226005": "Alambagh, Lucknow",
    "682011": "Ernakulam, Kochi",
    "682042": "Kakkanad, Kochi",
    "682001": "Fort Kochi",
    "395002": "Ring Road, Surat",
    "395009": "Adajan, Surat",
    "395007": "Vesu, Surat",
}


def _get_city_for_point(lat: float, lon: float, pincode: Optional[str] = None, address: Optional[str] = None) -> str:
    pin = str(pincode or "").strip()
    if pin:
        if pin.startswith("11") or pin.startswith("12") or pin.startswith("20"):
            return "Delhi/NCR"
        elif pin.startswith("40"):
            return "Mumbai"
        elif pin.startswith("56"):
            return "Bengaluru"
        elif pin.startswith("50"):
            return "Hyderabad"
        elif pin.startswith("60"):
            return "Chennai"
        elif pin.startswith("70") or pin.startswith("71"):
            return "Kolkata"
        elif pin.startswith("41"):
            return "Pune"
        elif pin.startswith("38") or pin.startswith("382"):
            return "Ahmedabad"
        elif pin.startswith("30"):
            return "Jaipur"
        elif pin.startswith("22"):
            return "Lucknow"
        elif pin.startswith("68"):
            return "Kochi"
        elif pin.startswith("39"):
            return "Surat"

    if address:
        addr_lower = address.lower()
        if "delhi" in addr_lower or "noida" in addr_lower or "gurugram" in addr_lower:
            return "Delhi/NCR"
        if "mumbai" in addr_lower:
            return "Mumbai"
        if "bengaluru" in addr_lower or "bangalore" in addr_lower:
            return "Bengaluru"
        if "hyderabad" in addr_lower:
            return "Hyderabad"
        if "chennai" in addr_lower:
            return "Chennai"
        if "kolkata" in addr_lower:
            return "Kolkata"
        if "pune" in addr_lower:
            return "Pune"
        if "ahmedabad" in addr_lower or "gandhinagar" in addr_lower:
            return "Ahmedabad"

    if 28.0 <= lat <= 29.2 and 76.5 <= lon <= 77.8:
        return "Delhi/NCR"
    elif 18.7 <= lat <= 19.5 and 72.6 <= lon <= 73.3:
        return "Mumbai"
    elif 12.7 <= lat <= 13.3 and 77.3 <= lon <= 77.9:
        return "Bengaluru"
    elif 17.1 <= lat <= 17.7 and 78.1 <= lon <= 78.7:
        return "Hyderabad"
    elif 12.8 <= lat <= 13.3 and 80.0 <= lon <= 80.5:
        return "Chennai"
    elif 22.3 <= lat <= 22.9 and 88.1 <= lon <= 88.6:
        return "Kolkata"
    elif 18.3 <= lat <= 18.8 and 73.6 <= lon <= 74.1:
        return "Pune"
    elif 22.8 <= lat <= 23.3 and 72.3 <= lon <= 72.8:
        return "Ahmedabad"

    return "India (Other)"


def _parse_time_filter(tf: Optional[str]) -> Optional[datetime]:
    if not tf:
        return None
    tf_str = str(tf).strip().lower()
    now = datetime.now(timezone.utc)
    if tf_str in {"24h", "1d", "today"}:
        return now - timedelta(hours=24)
    elif tf_str in {"7d", "7days", "week"}:
        return now - timedelta(days=7)
    elif tf_str in {"30d", "30days", "month"}:
        return now - timedelta(days=30)
    elif tf_str in {"recent", "1h"}:
        return now - timedelta(hours=1)
    try:
        dt = datetime.fromisoformat(str(tf).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_term_ids(raw: str) -> list:
    raw = (raw or "").strip()
    if not raw or raw == "[]":
        return []
    try:
        val = ast.literal_eval(raw)
        if isinstance(val, list):
            return [str(x) for x in val]
    except Exception:
        pass
    return [p.strip() for p in raw.split(",") if p.strip()]


def _inr(amount: float) -> str:
    return f"₹{amount:,.0f}"


def _window_label(start, end) -> str:
    def fmt(v):
        if isinstance(v, datetime):
            return v.astimezone(timezone.utc).strftime("%H:%M")
        s = str(v)
        return s[11:16] if len(s) >= 16 else s
    return f"{fmt(start)} – {fmt(end)} UTC"


def _bank_from_terminal(tid: str) -> str:
    parts = tid.split("-")
    return parts[1] if len(parts) > 1 else "Bank"


def _term_type(t: dict) -> str:
    raw = str(t.get("terminal_type", "ATM_KIOSK"))
    return "AEPS_MICRO_ATM" if "AEPS" in raw.upper() else "BANK_ATM"


def _address(t: dict) -> str:
    pin = str(t.get("district_pincode") or t.get("pincode") or "")
    city = PIN_LABEL.get(pin, t.get("district") or "India")
    return f"{t.get('terminal_id')}, {city} {pin}".strip()


def _marker(t: dict, confidence: int, window: str, risk: str) -> dict:
    return {
        "id": t["terminal_id"],
        "address": _address(t),
        "type": _term_type(t),
        "latitude": float(t.get("latitude") or 0),
        "longitude": float(t.get("longitude") or 0),
        "riskLevel": risk,
        "confidencePercent": confidence,
        "cashoutWindow": window,
        "bankName": _bank_from_terminal(t["terminal_id"]),
    }


def _nearby(target: dict, terminals: List[dict], limit: int = 5) -> List[dict]:
    lat, lon = float(target.get("latitude") or 0), float(target.get("longitude") or 0)
    target_id = target.get("terminal_id") or target.get("id")
    # Quick bounding box filter (+/- 0.35 deg approx 40km)
    candidates = [
        t for t in terminals
        if t.get("terminal_id") != target_id
        and abs(float(t.get("latitude") or 0) - lat) < 0.35
        and abs(float(t.get("longitude") or 0) - lon) < 0.35
    ]
    if not candidates:
        candidates = [t for t in terminals if t.get("terminal_id") != target_id][:50]
        
    scored = []
    for t in candidates:
        km = _haversine_km(lat, lon, float(t.get("latitude") or 0), float(t.get("longitude") or 0))
        scored.append((km, t))
    scored.sort(key=lambda x: x[0])
    out = []
    for km, t in scored[:limit]:
        item = _marker(t, 40, "Monitor", "MEDIUM")
        item["distanceKm"] = round(km, 2)
        out.append(item)
    return out


def _trail(graph: GraphStore, account_id: str, predicted_id: str) -> dict:
    hops: List[TransactionEvent] = []
    cur = account_id
    seen = {account_id}
    for _ in range(8):
        incoming = graph.transactions_involving(cur, direction="in")
        if not incoming:
            break
        leg = max(incoming, key=lambda e: e.amount_inr)
        if leg.source_account_id in seen:
            break
        hops.append(leg)
        seen.add(leg.source_account_id)
        cur = leg.source_account_id
    hops.reverse()
    nodes = []
    edges = []
    order: List[str] = []
    for hop in hops:
        if hop.source_account_id not in order:
            order.append(hop.source_account_id)
        if hop.target_account_id not in order:
            order.append(hop.target_account_id)
    if account_id not in order:
        order.append(account_id)
    if predicted_id not in order:
        order.append(predicted_id)
    for i, acc in enumerate(order):
        kind = "terminal" if acc == predicted_id else ("victim" if i == 0 else ("aggregator" if acc == account_id else "mule"))
        nodes.append({"label": acc, "type": kind, "accountHint": acc})
    idx = {acc: i for i, acc in enumerate(order)}
    for hop in hops:
        edges.append({
            "fromIndex": idx[hop.source_account_id],
            "toIndex": idx[hop.target_account_id],
            "label": hop.transaction_id,
            "amount": _inr(hop.amount_inr),
            "timestamp": str(hop.timestamp),
            "channel": hop.payment_channel,
        })
    if predicted_id in idx and account_id in idx and predicted_id != account_id:
        edges.append({
            "fromIndex": idx[account_id],
            "toIndex": idx[predicted_id],
            "label": "predicted-cashout",
            "amount": "Predicted cash-out",
            "timestamp": "Predicted window",
            "channel": "ATM / AEPS",
        })
    return {"nodes": nodes, "edges": edges}


def _load_csv(graph: GraphStore) -> None:
    acc_path = REPO_ROOT / "data-generator" / "data" / "accounts.csv"
    txn_path = REPO_ROOT / "data-generator" / "data" / "transactions.csv"
    if acc_path.exists():
        with open(acc_path, encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i > 1000:
                    break
                aid = row.get("account_id") or ""
                if not aid:
                    continue
                sim = f"SIM-{aid[-5:]}-{abs(hash(aid)) % 9000 + 1000}"
                graph.add_account_metadata(AccountNodeMetadata(
                    account_id=aid,
                    account_tier=row.get("account_tier") or "normal",
                    account_age_days=int(float(row.get("account_age_days") or 0)),
                    historical_terminal_ids=_parse_term_ids(row.get("historical_terminal_ids") or ""),
                    kyc_identity_id=row.get("kyc_identity_id") or None,
                ))
                graph.accounts.setdefault(aid, {})["sim_hash"] = sim
                graph.accounts[aid]["device_fingerprint"] = row.get("primary_device_fingerprint") or ""
    if txn_path.exists():
        with open(txn_path, encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i > 500:
                    break
                try:
                    graph.add_transaction(TransactionEvent.from_dict(row))
                except Exception:
                    continue


def _boost_geo(graph: GraphStore, geo_id: str, base: datetime) -> None:
    """Give the Mumbai→Hyderabad account enough corroborating activity to alert."""
    for i in range(6):
        src = f"ACC-GEOFEED{i:02d}"
        graph.add_account_metadata(AccountNodeMetadata(account_id=src, account_tier="mule_l1", account_age_days=6))
        graph.add_transaction(TransactionEvent(
            transaction_id=f"TXN-GEO-FEED-{i:03d}",
            source_account_id=src,
            target_account_id=geo_id,
            amount_inr=8000 + i * 250,
            timestamp=base - timedelta(minutes=40, seconds=i * 8),
            payment_channel="UPI",
            device_fingerprint="DEV-GEO-SHARED",
        ))


def _withdrawals_for(account_id: str, terminals: List[dict], graph: GraphStore, blocked: bool):
    usages = graph.recent_terminal_usages(account_id, limit=8)
    by_id = {t["terminal_id"]: t for t in terminals}
    out = []
    counts: Dict[str, int] = {}
    for u in usages:
        tid = u["terminal_id"]
        counts[tid] = counts.get(tid, 0) + 1
        term = by_id.get(tid, {})
        status = "BLOCKED" if blocked else "FLAGGED"
        if counts[tid] >= 3:
            status = "INTERCEPTED"
        ts = u["timestamp"]
        ts_s = ts.isoformat() if isinstance(ts, datetime) else str(ts)
        out.append({
            "attemptId": f"{account_id}-{tid}-{counts[tid]}",
            "time": ts_s,
            "amount": "₹10,000",
            "terminalId": tid,
            "location": _address(term) if term else tid,
            "status": status,
            "latitude": u.get("latitude"),
            "longitude": u.get("longitude"),
        })
    if account_id.startswith("ACC-GEO") and len(out) < 3:
        hyd = by_id.get("ATM-ICICI-HYD-903") or terminals[0]
        for n in range(3):
            out.append({
                "attemptId": f"{account_id}-repeat-{n+1}",
                "time": (datetime.now(timezone.utc) - timedelta(minutes=4 - n)).isoformat(),
                "amount": "₹10,000",
                "terminalId": hyd["terminal_id"],
                "location": _address(hyd),
                "status": "INTERCEPTED" if n == 2 else "BLOCKED",
                "latitude": hyd.get("latitude"),
                "longitude": hyd.get("longitude"),
            })
        counts[hyd["terminal_id"]] = 3
    repeat_tid = max(counts, key=counts.get) if counts else None
    return out, {
        "accountId": account_id,
        "terminalId": repeat_tid,
        "attempts": counts.get(repeat_tid, 0) if repeat_tid else 0,
        "escalation": (
            "PERSISTENT_TERMINAL_RISK" if (repeat_tid and counts.get(repeat_tid, 0) >= 3)
            else "ELEVATED_RISK" if (repeat_tid and counts.get(repeat_tid, 0) == 2)
            else "MONITORED"
        ),
        "multiplier": 1.0 + 0.25 * max(0, (counts.get(repeat_tid, 0) if repeat_tid else 0) - 1),
    }


def _build_layering_provenance(graph: GraphStore, base: datetime) -> str:
    victim = "ACC-VIC-DELHI"
    mule1 = "ACC-MULE-L1B"
    mule2 = "ACC-MULE-L2C"
    aggr = "ACC-AGGR-NOIDA"
    graph.add_account_metadata(AccountNodeMetadata(account_id=victim, account_tier="victim", account_age_days=850))
    graph.add_account_metadata(AccountNodeMetadata(account_id=mule1, account_tier="mule_l1", account_age_days=8, historical_terminal_ids=["ATM-SBI-ND-042"]))
    graph.add_account_metadata(AccountNodeMetadata(account_id=mule2, account_tier="mule_l2", account_age_days=5, historical_terminal_ids=["ATM-SBI-ND-042"]))
    graph.add_account_metadata(AccountNodeMetadata(account_id=aggr, account_tier="aggregator", account_age_days=3, historical_terminal_ids=["ATM-SBI-ND-042"], district_pincode="201301"))
    t = base - timedelta(minutes=15)
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-ROOT-00101", source_account_id=victim, target_account_id=mule1,
        amount_inr=100000, timestamp=t, payment_channel="UPI", device_fingerprint="DEV-VIC-01"))
    t += timedelta(minutes=2)
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-HOP-00102", source_account_id=mule1, target_account_id=mule2,
        amount_inr=99000, timestamp=t, payment_channel="IMPS", device_fingerprint="DEV-MULE-L1"))
    t += timedelta(minutes=2)
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-HOP-00103", source_account_id=mule2, target_account_id=aggr,
        amount_inr=96000, timestamp=t, payment_channel="UPI", device_fingerprint="DEV-MULE-L2"))
    return aggr


def _build_precomplaint_protection(graph: GraphStore, base: datetime) -> str:
    victim = "ACC-VIC-MUM"
    target = "ACC-PRECOMP-SBI"
    graph.add_account_metadata(AccountNodeMetadata(account_id=victim, account_tier="victim", account_age_days=950))
    graph.add_account_metadata(AccountNodeMetadata(account_id=target, account_tier="mule_l1", account_age_days=14, historical_terminal_ids=["ATM-SBI-ND-042"], district_pincode="201301"))
    graph.add_transaction(TransactionEvent(
        transaction_id="TXN-LEGIT-009", source_account_id="ACC-SALARY-CORP", target_account_id=target,
        amount_inr=20000, timestamp=base - timedelta(days=5), payment_channel="NEFT", device_fingerprint="DEV-CUSTOMER-NORMAL"))
    t = base - timedelta(minutes=10)
    for i in range(4):
        src = f"ACC-BURSTFEED{i:02d}"
        graph.add_account_metadata(AccountNodeMetadata(account_id=src, account_tier="victim", account_age_days=500))
        graph.add_transaction(TransactionEvent(
            transaction_id=f"TXN-BURST-{i:03d}", source_account_id=src, target_account_id=target,
            amount_inr=12500, timestamp=t + timedelta(seconds=i * 20), payment_channel="UPI", device_fingerprint="DEV-BURST-FEED"))
    return target


class CaseEngine:
    """In-memory operational store consumed by the Android app."""

    def __init__(self) -> None:
        self.graph = GraphStore()
        self.terminals: List[dict] = []
        self.cases: Dict[str, dict] = {}
        self.audit: List[dict] = []
        self.ledger = AuditLedger()
        self.store = Store()
        self.notification_service = NotificationService(store=self.store)
        self._build()

    def _build(self) -> None:
        term_nodes = scorer.load_terminals()
        self.terminals = [t.to_dict() for t in term_nodes]
        self.graph.load_terminals(self.terminals)
        base = datetime.now(timezone.utc)
        _load_csv(self.graph)
        ring = build_mule_identity_ring(self.graph, base)
        geo = build_geo_velocity_scenario(self.graph, base)
        _boost_geo(self.graph, geo, base)
        critical = build_critical_saturation_case(self.graph, base)
        layering = _build_layering_provenance(self.graph, base)
        precomp = _build_precomplaint_protection(self.graph, base)
        self.graph.record_terminal_usage(critical, "ATM-HDFC-Ce-001", base - timedelta(minutes=8))
        self.graph.record_terminal_usage(critical, "ATM-HDFC-Ce-001", base - timedelta(minutes=5))
        self.graph.record_terminal_usage(critical, "ATM-HDFC-Ce-001", base - timedelta(minutes=2))

        showcase = [ring[0], geo, critical, layering, precomp]
        tags = {
            ring[0]: "mule-ring",
            geo: "geo",
            critical: "critical",
            layering: "layering",
            precomp: "precomplaint",
        }
        for account_id in showcase:
            ev = scorer.evaluate_account(self.graph, account_id, as_of=base)
            alert = scorer.analyze(self.graph, account_id, terminals=term_nodes, as_of=base, notify_threshold=1)
            if alert is None:
                continue
            decision = decide_intervention(alert, ev.band)
            self.ledger.append({
                "complaint_id": alert.complaint_id,
                "flagged_account_id": account_id,
                "tier": decision.tier,
                "justification": decision.justification,
            })
            try:
                self.store.save_alert(alert, ev.band)
                self.store.save_intervention(alert.complaint_id, decision)
            except Exception:
                pass
            case = self._to_case(account_id, ev, alert, decision)
            if account_id in tags:
                case["demoTag"] = tags[account_id]
            self.cases[case["ncrpId"]] = case

        # Guarantee the three mentor scenarios are present even if scoring skipped them.
        for account_id, tag in ((ring[0], "mule-ring"), (geo, "geo"), (critical, "critical")):
            if not any(c.get("flaggedAccountId") == account_id for c in self.cases.values()):
                ev = scorer.evaluate_account(self.graph, account_id, as_of=base)
                alert = scorer.analyze(self.graph, account_id, terminals=term_nodes, as_of=base, notify_threshold=1)
                if alert:
                    decision = decide_intervention(alert, ev.band or "HIGH")
                    case = self._to_case(account_id, ev, alert, decision)
                    case["demoTag"] = tag
                    self.cases[case["ncrpId"]] = case

    def _to_case(self, account_id: str, ev, alert, decision) -> dict:
        predicted = alert.predicted_terminals[0] if alert.predicted_terminals else None
        term = next((t for t in self.terminals if predicted and t["terminal_id"] == predicted.terminal_id), None)
        if term is None:
            term = self.terminals[0] if self.terminals else {
                "terminal_id": "ATM-UNKNOWN", "latitude": 28.57, "longitude": 77.32,
                "terminal_type": "ATM_KIOSK", "district_pincode": "201301",
            }
        risk = ev.band if ev.band in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} else "HIGH"
        conf = int(round((alert.confidence or 0.6) * 100))
        window = _window_label(alert.predicted_window_start, alert.predicted_window_end)
        marker = _marker(term, max(conf, int(alert.risk_score * 100)), window, risk)
        nearby = _nearby(term, self.terminals)
        blocked = decision.tier in {"AUTO_FREEZE", "AUTO_HOLD"}
        attempts, repeat = _withdrawals_for(account_id, self.terminals, self.graph, blocked)
        signals = []
        for r in ev.rules:
            if r.severity <= 0:
                continue
            title, expl = PLAIN.get(r.name, (r.name.replace("_", " "), r.evidence))
            signals.append({
                "icon": "•",
                "name": title,
                "contributionPercent": int(round(r.points)),
                "explanation": expl if expl.endswith(".") else (r.evidence or expl),
                "technicalTag": f"{r.name}_rule",
            })
        signals.sort(key=lambda s: s["contributionPercent"], reverse=True)
        exposure = 0.0
        incoming = self.graph.transactions_involving(account_id, direction="in")
        if incoming:
            exposure = sum(e.amount_inr for e in incoming[-12:])
        legitimate = max(5000.0, exposure * 0.15)
        sim = (self.graph.accounts.get(account_id) or {}).get("sim_hash") or f"SIM-{account_id[-4:]}"
        device = next(iter(self.graph._account_devices.get(account_id) or ["unknown"]), "unknown")
        status = "PENDING"
        digital = False
        atm_block = False
        if decision.tier == "AUTO_FREEZE":
            status = "BANK_HOLD"
            digital = True
            atm_block = True
        elif decision.tier == "AUTO_HOLD":
            status = "BANK_HOLD"
            digital = True
        summary = (
            f"{ev.band} risk on {account_id}. {signals[0]['name'] if signals else 'Multiple rules fired'}. "
            f"Predicted cash-out {marker['id']} ({marker['address']}) in window {window}."
        )
        if any(r.name == "geo_velocity" and r.severity > 0 for r in ev.rules):
            summary = (
                f"Same account used in Mumbai then Hyderabad within minutes — physically impossible. "
                f"Predicted next cash-out {marker['id']}."
            )
        elif any(r.name == "identity_cluster" and r.severity > 0 for r in ev.rules):
            n = len(self.graph.accounts_sharing_kyc_identity(account_id)) + 1
            if n >= 8:
                summary = (
                    f"{n} accounts share one KYC identity and are moving funds toward {marker['id']}."
                )
        elif account_id == "ACC-AGGR-NOIDA":
            summary = (
                f"₹1,00,000 rapid 4-hop layering chain from ACC-VIC-DELHI to ACC-AGGR-NOIDA. "
                f"Predicted cash-out {marker['id']}."
            )
        elif account_id == "ACC-PRECOMP-SBI":
            summary = (
                "Provisional pre-complaint hold placed: ₹20,000 legitimate funds available, ₹50,000 suspicious exposure restricted. "
                "Unblock eligible only after customer verification."
            )
            legitimate = 20000.0
            exposure = 50000.0
            status = "BANK_HOLD"
            digital = True
        lifecycle = "PRE_COMPLAINT_INTERVENTION"
        # Ensure initial HIGH_RISK_CASE notification is recorded if risk is significant
        if risk in ("HIGH", "CRITICAL") or (ev.score >= 60):
            try:
                self.notification_service.notify(NotificationEvent(
                    event_type=NotificationEventType.HIGH_RISK_CASE,
                    case_id=alert.complaint_id,
                    account_id=account_id,
                    amount=exposure or (alert.risk_score * 100000),
                    terminal_id=marker["id"],
                    terminal_location=marker["address"],
                    confidence=alert.confidence or (conf / 100.0),
                    risk_score=alert.risk_score,
                    evidence=list(alert.evidence),
                    status=status,
                    details={"band": risk, "interventionTier": decision.tier},
                ))
            except Exception:
                pass

        notif_summary = self.notification_service.get_case_notification_summary(alert.complaint_id)

        return {
            "ncrpId": alert.complaint_id,
            "reportedLoss": _inr(exposure or alert.risk_score * 100000),
            "timeElapsed": "Live feed",
            "victimAccount": account_id,
            "flaggedAccountId": account_id,
            "status": status,
            "summary": summary,
            "targetTerminal": marker,
            "nearbyTerminals": nearby,
            "corridor": alert.corridor.to_dict() if (alert and hasattr(alert, "corridor") and alert.corridor) else None,
            "moneyTrail": _trail(self.graph, account_id, marker["id"]),
            "riskBreakdown": {"totalPercent": int(round(ev.score)), "signals": signals[:8]},
            "complaintId": None,
            "confirmationState": "PENDING_CONFIRMATION",
            "transactionCount": len(incoming),
            "digitalBlockActive": digital,
            "atmBlockActive": atm_block,
            "lifecycle": lifecycle,
            "interventionTier": decision.tier,
            "justification": decision.justification,
            "legitimateBalance": round(legitimate, 2),
            "suspiciousExposure": round(exposure, 2),
            "withdrawalAttempts": attempts,
            "repeatActivity": repeat,
            "simHash": sim,
            "deviceFingerprint": str(device),
            "confidencePercent": conf,
            "evidence": list(alert.evidence),
            "notificationStatus": notif_summary.get("channels", {}),
            "notifications": notif_summary.get("items", []),
        }

    def list_cases(self, role: str = "BANK") -> List[dict]:
        items = list(self.cases.values())
        if role.upper().startswith("POLICE"):
            return [c for c in items if c["status"] in {"APPROVED", "EN_ROUTE"}]
        return items

    def get(self, ncrp_id: str) -> Optional[dict]:
        return self.cases.get(ncrp_id)

    def process_transaction(
        self,
        tx: Union[dict, TransactionEvent],
        as_of: Optional[datetime] = None,
    ) -> Optional[dict]:
        """Ingests a transaction event into the live GraphStore, persists it to SQLite,
        evaluates affected accounts against explainable detection rules, creates/updates
        high-risk cases, and triggers live WebSocket alert broadcasts."""
        if isinstance(tx, dict):
            event = TransactionEvent.from_dict(tx)
        elif isinstance(tx, TransactionEvent):
            event = tx
        else:
            log.warning(f"Invalid transaction payload type: {type(tx)}")
            return None

        # Add transaction to in-memory graph
        self.graph.add_transaction(event)

        # Save to SQLite persistence
        try:
            raw_tx = event.to_dict() if hasattr(event, "to_dict") else asdict(event)
            self.store.save_transaction(raw_tx)
        except Exception as e:
            log.warning(f"Failed to persist transaction to SQLite: {e}")

        eval_time = as_of or (event.timestamp_utc if hasattr(event, "timestamp_utc") else datetime.now(timezone.utc))
        term_nodes = scorer.load_terminals()
        flagged_case = None

        for account_id in (event.target_account_id, event.source_account_id):
            if not account_id or not account_id.startswith("ACC"):
                continue

            ev = scorer.evaluate_account(self.graph, account_id, as_of=eval_time)
            # Threshold for alert creation in live stream
            if ev.score >= 50:
                alert = scorer.analyze(self.graph, account_id, terminals=term_nodes, as_of=eval_time, notify_threshold=50)
                if alert is not None:
                    decision = decide_intervention(alert, ev.band)
                    new_case = self._to_case(account_id, ev, alert, decision)
                    new_case["demoTag"] = "live-stream"

                    # Check if an existing case for this account exists
                    existing = next((c for c in self.cases.values() if c.get("flaggedAccountId") == account_id), None)
                    if existing:
                        new_case["ncrpId"] = existing["ncrpId"]
                        if existing.get("status") in {"APPROVED", "DISMISSED", "FIELD_PATROL_DISPATCHED", "BANK_HOLD"}:
                            new_case["status"] = existing["status"]
                        self.cases[new_case["ncrpId"]] = new_case
                        self._log(new_case["ncrpId"], f"Live stream update: tx {event.transaction_id} (₹{event.amount_inr:,.0f})", new_case["status"], "Detection Engine")
                    else:
                        self.cases[new_case["ncrpId"]] = new_case
                        self._log(new_case["ncrpId"], f"Live alert generated: tx {event.transaction_id} on {account_id}", new_case["status"], "Detection Engine")

                    self.ledger.append({
                        "complaint_id": new_case["ncrpId"],
                        "flagged_account_id": account_id,
                        "tier": decision.tier,
                        "justification": decision.justification,
                        "transaction_id": event.transaction_id,
                    })

                    try:
                        self.store.save_alert(alert, ev.band)
                        self.store.save_intervention(new_case["ncrpId"], decision)
                    except Exception as e:
                        log.debug(f"SQLite save alert/intervention: {e}")

                    # Broadcast over WebSocket channel
                    try:
                        from api.server import sync_broadcast
                        sync_broadcast("NEW_ALERT", {
                            "case": new_case,
                            "message": f"🚨 High-Risk Fraud Alert: {new_case['ncrpId']} on {account_id}!",
                            "audit": self.audit[0] if self.audit else None,
                        })
                    except Exception as e:
                        log.debug(f"WebSocket broadcast error: {e}")

                    flagged_case = new_case

        return flagged_case

    def process_transactions_batch(
        self,
        txs: List[Union[dict, TransactionEvent]],
        as_of: Optional[datetime] = None,
    ) -> List[dict]:
        """Ingests a sequence of transactions, evaluating cases and returning all generated alerts."""
        cases = []
        for tx in txs:
            c = self.process_transaction(tx, as_of=as_of)
            if c and c not in cases:
                cases.append(c)
        return cases

    def _log(self, ncrp_id: str, action: str, status: str, officer: str = "Duty officer") -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M"),
            "officerName": officer,
            "ncrpId": ncrp_id,
            "action": action,
            "targetUnit": self.cases.get(ncrp_id, {}).get("targetTerminal", {}).get("bankName", "—"),
            "status": status,
        }
        self.audit.insert(0, entry)
        self.ledger.append({"complaint_id": ncrp_id, "action": action, "status": status, "justification": action})

    def act(self, ncrp_id: str, action: str, officer: str = "Duty officer") -> Optional[dict]:
        case = self.cases.get(ncrp_id)
        if not case:
            return None
        acc = case["flaggedAccountId"]
        if action == "hold":
            case["status"] = "BANK_HOLD"
            case["digitalBlockActive"] = True
            case["confirmationState"] = "PENDING_CONFIRMATION"
            self._bank(acc, "hold", case)
            self._log(ncrp_id, "Provisional digital hold placed (pre-complaint)", "BANK_HOLD", officer)
        elif action == "escalate":
            case["status"] = "APPROVED"
            case["atmBlockActive"] = True
            case["digitalBlockActive"] = True
            case["lifecycle"] = "POST_COMPLAINT_ESCALATED"
            case["complaintId"] = case["complaintId"] or ncrp_id
            self._bank(acc, "freeze", case)
            self._log(ncrp_id, "Forwarded to police with ATM/location pack", "APPROVED", officer)

            # Operational Notification: POLICE_ALERT_SENT & CASE_ESCALATED
            try:
                self.notification_service.notify(NotificationEvent(
                    event_type=NotificationEventType.POLICE_ALERT_SENT,
                    case_id=ncrp_id,
                    account_id=acc,
                    amount=case.get("suspiciousExposure") or 100000.0,
                    terminal_id=case.get("targetTerminal", {}).get("id"),
                    terminal_location=case.get("targetTerminal", {}).get("address"),
                    status="APPROVED",
                    details={"action": "escalate", "officer": officer},
                ))
                self.notification_service.notify(NotificationEvent(
                    event_type=NotificationEventType.CASE_ESCALATED,
                    case_id=ncrp_id,
                    account_id=acc,
                    amount=case.get("suspiciousExposure") or 100000.0,
                    status="APPROVED",
                    details={"action": "escalate", "officer": officer},
                ))
            except Exception:
                pass

        elif action == "dismiss":
            case["status"] = "DISMISSED"
            case["lifecycle"] = "RESOLVED"
            self._log(ncrp_id, "Dismissed as false positive", "DISMISSED", officer)
        elif action == "release":
            if case["status"] != "BANK_HOLD":
                return case
            if case["confirmationState"] != "CONFIRMED_LEGITIMATE":
                case["confirmationState"] = "CONFIRMED_LEGITIMATE"
            case["status"] = "RELEASED"
            case["digitalBlockActive"] = False
            case["atmBlockActive"] = False
            case["lifecycle"] = "RESOLVED"
            self._bank(acc, "unfreeze", case)
            self._log(ncrp_id, "Hold released after customer confirmed activity was legitimate", "RELEASED", officer)
        elif action == "confirm_customer":
            case["confirmationState"] = "CONFIRMED_LEGITIMATE"
            self._log(ncrp_id, "Bank official confirmed with customer — not malicious", "BANK_HOLD", officer)
        elif action == "file_complaint":
            case["complaintId"] = ncrp_id
            case["lifecycle"] = "POST_COMPLAINT_ESCALATED"
            case["atmBlockActive"] = True
            case["digitalBlockActive"] = True
            case["status"] = "BANK_HOLD"
            self._bank(acc, "freeze", case)
            self._log(ncrp_id, "NCRP complaint linked — online and physical ATM block", "BANK_HOLD", officer)
            try:
                self.notification_service.notify(NotificationEvent(
                    event_type=NotificationEventType.CASE_ESCALATED,
                    case_id=ncrp_id,
                    account_id=acc,
                    amount=case.get("suspiciousExposure") or 100000.0,
                    status="BANK_HOLD",
                    details={"action": "file_complaint", "officer": officer},
                ))
            except Exception:
                pass
        elif action == "simulate_withdraw":
            term = case["targetTerminal"]
            is_blocked = bool(case["digitalBlockActive"] or case["atmBlockActive"])
            status_label = "BLOCKED" if is_blocked else "FLAGGED"
            case["withdrawalAttempts"].append({
                "attemptId": f"live-{len(case['withdrawalAttempts'])+1}",
                "time": datetime.now(timezone.utc).isoformat(),
                "amount": "₹10,000",
                "terminalId": term["id"],
                "location": term["address"],
                "status": status_label,
                "latitude": term["latitude"],
                "longitude": term["longitude"],
            })
            case["lifecycle"] = "CASHOUT_ATTEMPT_DETECTED"
            n = len([a for a in case["withdrawalAttempts"] if a["terminalId"] == term["id"]])
            case["repeatActivity"] = {
                "accountId": acc,
                "terminalId": term["id"],
                "attempts": n,
                "escalation": "PERSISTENT_TERMINAL_RISK" if n >= 3 else "ELEVATED_RISK" if n == 2 else "MONITORED",
                "multiplier": 1.0 + 0.25 * max(0, n - 1),
            }
            self._log(ncrp_id, f"Cash-out attempt at {term['id']} recorded for police", "EN_ROUTE", officer)

            # Operational Notification: CASHOUT_ATTEMPT_DETECTED & WITHDRAWAL_BLOCKED
            try:
                self.notification_service.notify(NotificationEvent(
                    event_type=NotificationEventType.CASHOUT_ATTEMPT_DETECTED,
                    case_id=ncrp_id,
                    account_id=acc,
                    amount=10000.0,
                    terminal_id=term["id"],
                    terminal_location=term["address"],
                    status=status_label,
                    details={"is_blocked": is_blocked},
                ))
                if is_blocked:
                    self.notification_service.notify(NotificationEvent(
                        event_type=NotificationEventType.WITHDRAWAL_BLOCKED,
                        case_id=ncrp_id,
                        account_id=acc,
                        amount=10000.0,
                        terminal_id=term["id"],
                        terminal_location=term["address"],
                        status=status_label,
                        details={"is_blocked": True},
                    ))
            except Exception:
                pass

        # Refresh notification status on returned case object
        notif_summary = self.notification_service.get_case_notification_summary(ncrp_id)
        case["notificationStatus"] = notif_summary.get("channels", {})
        case["notifications"] = notif_summary.get("items", [])
        return case

    def _bank(self, account_id: str, action: str, case: dict) -> None:
        import json
        import urllib.request
        try:
            body = json.dumps({
                "reason": case.get("justification") or action,
                "complaint_id": case["ncrpId"],
                "confidence": (case.get("confidencePercent") or 0) / 100.0,
            }).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:8001/accounts/{account_id}/{action}",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=1.5)
        except Exception:
            pass

    def terminal_markers(self) -> List[dict]:
        by_id = {c["targetTerminal"]["id"]: c["targetTerminal"] for c in self.cases.values()}
        out = []
        for t in self.terminals:
            if t["terminal_id"] in by_id:
                out.append(by_id[t["terminal_id"]])
            else:
                out.append(_marker(t, 25, "No active prediction", "LOW"))
        return out

    def get_heatmap_points(
        self,
        case_id: Optional[str] = None,
        event_type: Optional[str] = None,
        city: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        aggregate: bool = True,
    ) -> dict:
        raw_points: List[dict] = []

        start_dt = _parse_time_filter(start_time)
        end_dt = _parse_time_filter(end_time)

        # 1. Active Case predicted cashout & nearby terminals
        for c_id, case in self.cases.items():
            if case_id and case_id != c_id:
                continue

            target = case.get("targetTerminal")
            if target:
                try:
                    lat_val = target.get("latitude")
                    lon_val = target.get("longitude")
                    if lat_val is not None and lon_val is not None:
                        lat = float(lat_val)
                        lon = float(lon_val)
                        if not (math.isnan(lat) or math.isnan(lon) or abs(lat) > 90 or abs(lon) > 180):
                            conf = (case.get("confidencePercent") or 80) / 100.0
                            weight = min(0.95, max(0.60, round(0.70 + 0.25 * conf, 2)))
                            raw_points.append({
                                "latitude": lat,
                                "longitude": lon,
                                "weight": weight,
                                "event_type": "PREDICTED_CASHOUT",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "case_id": c_id,
                                "terminal_id": target.get("id"),
                                "city": _get_city_for_point(lat, lon, address=target.get("address")),
                                "risk_level": "CRITICAL" if weight >= 0.85 else "HIGH",
                            })
                except (ValueError, TypeError):
                    pass

            for near in case.get("nearbyTerminals", []):
                try:
                    lat_val = near.get("latitude")
                    lon_val = near.get("longitude")
                    if lat_val is not None and lon_val is not None:
                        lat = float(lat_val)
                        lon = float(lon_val)
                        if not (math.isnan(lat) or math.isnan(lon) or abs(lat) > 90 or abs(lon) > 180):
                            weight = round(min(0.80, max(0.40, (near.get("confidencePercent") or 40) / 100.0)), 2)
                            raw_points.append({
                                "latitude": lat,
                                "longitude": lon,
                                "weight": weight,
                                "event_type": "PREDICTED_CASHOUT",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "case_id": c_id,
                                "terminal_id": near.get("id"),
                                "city": _get_city_for_point(lat, lon, address=near.get("address")),
                                "risk_level": near.get("riskLevel", "MEDIUM"),
                            })
                except (ValueError, TypeError):
                    pass

            # 2. Withdrawal Attempts & Blocked Withdrawals
            for att in case.get("withdrawalAttempts", []):
                try:
                    lat_val = att.get("latitude") or (target.get("latitude") if target else None)
                    lon_val = att.get("longitude") or (target.get("longitude") if target else None)
                    if lat_val is not None and lon_val is not None:
                        lat = float(lat_val)
                        lon = float(lon_val)
                        if not (math.isnan(lat) or math.isnan(lon) or abs(lat) > 90 or abs(lon) > 180):
                            status = str(att.get("status", "FLAGGED")).upper()
                            is_blocked = status in {"BLOCKED", "INTERCEPTED"}
                            etype = "BLOCKED_WITHDRAWALS" if is_blocked else "WITHDRAWAL_ATTEMPTS"
                            weight = 0.90 if is_blocked else 0.70
                            ts = att.get("time") or datetime.now(timezone.utc).isoformat()
                            raw_points.append({
                                "latitude": lat,
                                "longitude": lon,
                                "weight": weight,
                                "event_type": etype,
                                "timestamp": ts,
                                "case_id": c_id,
                                "terminal_id": att.get("terminalId"),
                                "city": _get_city_for_point(lat, lon, address=target.get("address") if target else None),
                                "risk_level": "CRITICAL" if is_blocked else "HIGH",
                            })
                except (ValueError, TypeError):
                    pass

            # 3. Repeated Terminal Activity
            rep = case.get("repeatActivity")
            if rep and rep.get("attempts", 0) >= 2:
                tid = rep.get("terminalId")
                term = next((t for t in self.terminals if t.get("terminal_id") == tid), None)
                if term:
                    try:
                        lat_val = term.get("latitude")
                        lon_val = term.get("longitude")
                        if lat_val is not None and lon_val is not None:
                            lat = float(lat_val)
                            lon = float(lon_val)
                            if not (math.isnan(lat) or math.isnan(lon) or abs(lat) > 90 or abs(lon) > 180):
                                mult = float(rep.get("multiplier") or 1.25)
                                weight = min(1.0, round(0.75 * mult, 2))
                                raw_points.append({
                                    "latitude": lat,
                                    "longitude": lon,
                                    "weight": weight,
                                    "event_type": "REPEATED_TERMINAL_ACTIVITY",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "case_id": c_id,
                                    "terminal_id": tid,
                                    "city": _get_city_for_point(lat, lon, pincode=term.get("district_pincode")),
                                    "risk_level": "CRITICAL" if weight >= 0.85 else "HIGH",
                                })
                    except (ValueError, TypeError):
                        pass

            # 4. Confirmed Fraud
            if case.get("status") in {"BANK_HOLD", "APPROVED"} or case.get("lifecycle") in {"POST_COMPLAINT_ESCALATED", "CASHOUT_ATTEMPT_DETECTED"}:
                if target:
                    try:
                        lat_val = target.get("latitude")
                        lon_val = target.get("longitude")
                        if lat_val is not None and lon_val is not None:
                            lat = float(lat_val)
                            lon = float(lon_val)
                            if not (math.isnan(lat) or math.isnan(lon) or abs(lat) > 90 or abs(lon) > 180):
                                raw_points.append({
                                    "latitude": lat,
                                    "longitude": lon,
                                    "weight": 1.0,
                                    "event_type": "CONFIRMED_FRAUD",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "case_id": c_id,
                                    "terminal_id": target.get("id"),
                                    "city": _get_city_for_point(lat, lon, address=target.get("address")),
                                    "risk_level": "CRITICAL",
                                })
                    except (ValueError, TypeError):
                        pass

        # 5. Suspicious Terminal Activity from terminal pool
        if not case_id:
            for t in self.terminals:
                tid = t.get("terminal_id")
                if any(p.get("terminal_id") == tid for p in raw_points):
                    continue
                try:
                    lat_val = t.get("latitude")
                    lon_val = t.get("longitude")
                    if lat_val is not None and lon_val is not None:
                        lat = float(lat_val)
                        lon = float(lon_val)
                        if not (lat == 0 and lon == 0) and not (math.isnan(lat) or math.isnan(lon) or abs(lat) > 90 or abs(lon) > 180):
                            raw_points.append({
                                "latitude": lat,
                                "longitude": lon,
                                "weight": 0.45,
                                "event_type": "SUSPICIOUS_ACTIVITY",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "case_id": None,
                                "terminal_id": tid,
                                "city": _get_city_for_point(lat, lon, pincode=t.get("district_pincode")),
                                "risk_level": "MEDIUM",
                            })
                except (ValueError, TypeError):
                    pass

        # Filtering phase
        filtered: List[dict] = []
        for p in raw_points:
            lat_v, lon_v = p.get("latitude"), p.get("longitude")
            if lat_v is None or lon_v is None:
                continue
            try:
                lat_f, lon_f = float(lat_v), float(lon_v)
                if math.isnan(lat_f) or math.isnan(lon_f) or abs(lat_f) > 90 or abs(lon_f) > 180:
                    continue
            except (ValueError, TypeError):
                continue

            if event_type and event_type.upper() != "ALL":
                if p["event_type"].upper() != event_type.upper():
                    continue

            if city:
                c_target = city.strip().lower()
                c_actual = p["city"].strip().lower()
                if c_target not in c_actual and c_actual not in c_target:
                    continue

            if start_dt or end_dt:
                ts_str = p.get("timestamp")
                if ts_str:
                    try:
                        p_dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                        if p_dt.tzinfo is None:
                            p_dt = p_dt.replace(tzinfo=timezone.utc)
                        else:
                            p_dt = p_dt.astimezone(timezone.utc)

                        if start_dt and p_dt < start_dt:
                            continue
                        if end_dt and p_dt > end_dt:
                            continue
                    except Exception:
                        pass

            filtered.append(p)

        # Aggregation phase
        final_points = filtered
        if aggregate and filtered:
            clusters: Dict[tuple, List[dict]] = {}
            for p in filtered:
                key = (round(p["latitude"], 3), round(p["longitude"], 3))
                clusters.setdefault(key, []).append(p)

            aggregated: List[dict] = []
            priority_map = {
                "CONFIRMED_FRAUD": 6,
                "BLOCKED_WITHDRAWALS": 5,
                "REPEATED_TERMINAL_ACTIVITY": 4,
                "PREDICTED_CASHOUT": 3,
                "WITHDRAWAL_ATTEMPTS": 2,
                "SUSPICIOUS_ACTIVITY": 1,
            }

            for (grid_lat, grid_lon), group in clusters.items():
                max_w = max(g["weight"] for g in group)
                count = len(group)
                agg_w = min(1.0, round(max_w + 0.15 * (count - 1), 2))
                best_p = max(group, key=lambda x: (priority_map.get(x["event_type"], 0), x["weight"]))

                aggregated.append({
                    "latitude": best_p["latitude"],
                    "longitude": best_p["longitude"],
                    "weight": agg_w,
                    "event_type": best_p["event_type"],
                    "timestamp": best_p["timestamp"],
                    "case_id": best_p["case_id"],
                    "terminal_id": best_p["terminal_id"],
                    "city": best_p["city"],
                    "risk_level": "CRITICAL" if agg_w >= 0.85 else ("HIGH" if agg_w >= 0.65 else "MEDIUM"),
                })
            final_points = aggregated

        event_counts: Dict[str, int] = {}
        cities_set = set()
        for p in final_points:
            event_counts[p["event_type"]] = event_counts.get(p["event_type"], 0) + 1
            cities_set.add(p["city"])

        return {
            "points": final_points,
            "summary": {
                "total_points": len(final_points),
                "event_counts": event_counts,
                "cities_represented": sorted(list(cities_set)),
            }
        }

