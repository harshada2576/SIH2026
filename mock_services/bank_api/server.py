"""mock_services/bank_api/server.py — a fake bank, for the demo only.

Deliberately built on the Python standard library only (http.server) — zero
pip installs required, which matters when you're wiring this together the
night before a demo. Simulates 3 named banks (accounts are deterministically
assigned to one via hash) with in-memory account status: ACTIVE, HOLD,
FROZEN, PROVISIONAL_HOLD, SELECTIVE_HOLD.

Endpoints:
  POST /accounts/{account_id}/freeze   {"reason": "...", "complaint_id": "...", "confidence": 0.9}
  POST /accounts/{account_id}/hold     (same body)
  POST /accounts/{account_id}/selective_hold (same body + amounts)
  POST /accounts/{account_id}/notify   (same body)  -- soft alert, no status change
  POST /accounts/{account_id}/unfreeze
  GET  /accounts/{account_id}          -- current status + action history
  GET  /accounts                       -- every account this server has seen
  POST /terminal/block                 -- physical ATM block request
  GET  /terminal/blocks                -- active terminal blocks
  POST /terminal/attempt               -- process cashout attempt via WithdrawalGeoIntelligence
  GET  /terminal/attempts              -- list cashout attempts
  POST /confirmations/request          -- create PENDING_CONFIRMATION
  POST /confirmations/{id}/respond     -- respond CONFIRMED_LEGITIMATE or CONFIRMED_FRAUD
  GET  /confirmations/{id}             -- get confirmation record
  GET  /confirmations                  -- get confirmation records
  POST /transaction-control/evaluate   -- evaluate transfer or withdrawal channel control
  GET  /recovery-workflows             -- list recovery workflows
  GET  /recovery-workflows/{id}        -- get recovery workflow
  GET  /chains                         -- list all recent provenance chains
  GET  /chains/{id}                    -- get specific provenance chain
  GET  /chains/account/{id}/exposure   -- get account exposure (legitimate vs suspicious)
  GET  /chains/account/{id}/convergent -- get convergent multi-victim chains for account
  POST /chains/track-descendant        -- track a downstream descendant transaction
  GET  /recovery-cases                 -- list formal recovery cases
  GET  /recovery-cases/{id}            -- get recovery case
  POST /recovery-cases/{id}/status     -- update recovery case state & simulated actions
  GET  /cases/{id}/withdrawals         -- get withdrawal attempts for case
  GET  /cases/{id}/locations           -- get chronological location history for case
  GET  /terminals/{id}/nearby          -- get ranked nearby terminals
  GET  /accounts/{id}/terminal-history -- get account terminal recurrence history
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from mock_services.bank_api.police_ui import POLICE_APP_HTML
from detection.transaction_control import TransactionControlManager
from pipeline.case_orchestrator import CaseOrchestrator
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from pipeline.police_alert_delivery import PoliceAlertManager
from shared.persistence import Store

BANKS = ["HDFC-SIM", "ICICI-SIM", "SBI-SIM"]

# account_id -> {"bank": str, "status": str, "existing_balance": float, "held_balance": float, "available_balance": float, "history": [ {...} ]}
_ACCOUNTS: dict = {}
_TERMINAL_BLOCKS: dict = {}   # terminal_id -> [ block_reqs ]
_WITHDRAWAL_ATTEMPTS: list = [] # list of attempt logs

_STORE: Optional[Store] = None
_CONTROL_MGR: Optional[TransactionControlManager] = None
_TRACE_ENGINE: Optional[FundTraceabilityEngine] = None
_GEO_INTEL: Optional[WithdrawalGeoIntelligence] = None
_POLICE_MGR: Optional[PoliceAlertManager] = None
_ORCHESTRATOR: Optional[CaseOrchestrator] = None


def _get_store() -> Store:
    global _STORE
    if _STORE is None:
        _STORE = Store()
    return _STORE


def _get_control_manager() -> TransactionControlManager:
    global _CONTROL_MGR
    if _CONTROL_MGR is None:
        _CONTROL_MGR = TransactionControlManager(store=_get_store())
    return _CONTROL_MGR


def _get_trace_engine() -> FundTraceabilityEngine:
    global _TRACE_ENGINE
    if _TRACE_ENGINE is None:
        _TRACE_ENGINE = FundTraceabilityEngine(store=_get_store())
    return _TRACE_ENGINE


def _get_geo_intel() -> WithdrawalGeoIntelligence:
    global _GEO_INTEL
    if _GEO_INTEL is None:
        _GEO_INTEL = WithdrawalGeoIntelligence(store=_get_store())
    return _GEO_INTEL


def _get_police_manager() -> PoliceAlertManager:
    global _POLICE_MGR
    if _POLICE_MGR is None:
        _POLICE_MGR = PoliceAlertManager(
            store=_get_store(),
            trace_engine=_get_trace_engine(),
            geo_intel=_get_geo_intel(),
        )
    return _POLICE_MGR


def _get_orchestrator() -> CaseOrchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        _ORCHESTRATOR = CaseOrchestrator(
            store=_get_store(),
            control_mgr=_get_control_manager(),
            trace_engine=_get_trace_engine(),
            geo_intel=_get_geo_intel(),
            police_mgr=_get_police_manager(),
        )
    return _ORCHESTRATOR


def _bank_for(account_id: str) -> str:
    h = int(hashlib.sha256(account_id.encode()).hexdigest(), 16)
    return BANKS[h % len(BANKS)]


def _get_or_create(account_id: str) -> dict:
    if account_id not in _ACCOUNTS:
        _ACCOUNTS[account_id] = {
            "bank": _bank_for(account_id),
            "status": "ACTIVE",
            "existing_balance": 20000.0,
            "held_balance": 0.0,
            "available_balance": 20000.0,
            "selective_hold": None,
            "history": [],
        }
    return _ACCOUNTS[account_id]


def _record_action(account_id: str, action: str, body: dict) -> dict:
    acc = _get_or_create(account_id)
    entry = {
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": body.get("reason", ""),
        "complaint_id": body.get("complaint_id", body.get("case_id", "")),
        "confidence": body.get("confidence"),
        "details": body,
    }
    acc["history"].append(entry)

    if action == "selective_hold":
        suspicious_amt = float(body.get("suspicious_amount", body.get("protected_amount", 100000.0)))
        existing_bal = float(body.get("existing_balance", acc.get("existing_balance", 20000.0)))
        protected_amt = float(body.get("protected_amount", suspicious_amt))

        acc["existing_balance"] = existing_bal
        acc["held_balance"] = protected_amt
        acc["available_balance"] = existing_bal  # Existing legitimate funds stay untouched!
        acc["status"] = "PROVISIONAL_HOLD" if body.get("pre_complaint", True) else "SELECTIVE_HOLD"
        acc["selective_hold"] = {
            "suspicious_amount": suspicious_amt,
            "protected_amount": protected_amt,
            "existing_balance": existing_bal,
            "source_transaction_id": body.get("source_transaction_id", ""),
            "chain_reference": body.get("chain_reference", ""),
            "reason": body.get("reason", ""),
            "timestamp": entry["timestamp"],
            "status": "ACTIVE",
        }
        print(f"[BANK:{acc['bank']}] SELECTIVE_HOLD on {account_id} | "
              f"Protected Suspicious: ₹{protected_amt:,.2f} | Unaffected Existing: ₹{existing_bal:,.2f} "
              f"(Reason: {entry['reason']})")
    elif action == "freeze":
        acc["status"] = "FROZEN"
        acc["available_balance"] = 0.0
        acc["held_balance"] = acc["existing_balance"] + (acc["selective_hold"]["suspicious_amount"] if acc.get("selective_hold") else 0.0)
        print(f"[BANK:{acc['bank']}] FULL FREEZE on {account_id} (complaint {entry['complaint_id']})")
    elif action == "hold":
        acc["status"] = "HOLD" if acc["status"] != "FROZEN" else acc["status"]
        print(f"[BANK:{acc['bank']}] HOLD on {account_id}")
    elif action == "unfreeze":
        acc["status"] = "ACTIVE"
        acc["held_balance"] = 0.0
        acc["available_balance"] = acc["existing_balance"]
        acc["selective_hold"] = None
        print(f"[BANK:{acc['bank']}] UNFREEZE on {account_id}")
    else:
        print(f"[BANK:{acc['bank']}] {action.upper()} on {account_id}")

    return acc


def _record_terminal_block(body: dict) -> dict:
    tid = str(body.get("terminal_id", "UNKNOWN"))
    record = {
        "terminal_id": tid,
        "case_id": body.get("case_id", ""),
        "reason": body.get("reason", "PREDICTED_CASH_EGRESS"),
        "action": body.get("action", "BLOCK_WITHDRAWAL"),
        "valid_from": body.get("valid_from", datetime.now(timezone.utc).isoformat()),
        "valid_until": body.get("valid_until", ""),
        "account_id": body.get("account_id"),
        "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if tid not in _TERMINAL_BLOCKS:
        _TERMINAL_BLOCKS[tid] = []
    _TERMINAL_BLOCKS[tid].append(record)
    print(f"[TERMINAL_CBS] Physical Withdrawal Block REQUESTED for Terminal {tid} | Case {record['case_id']} | Reason: {record['reason']}")
    return record


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        store = _get_store()
        ctrl = _get_control_manager()
        trace = _get_trace_engine()
        geo = _get_geo_intel()

        if parts == ["accounts"]:
            self._send_json(200, {"accounts": _ACCOUNTS})
        elif len(parts) == 2 and parts[0] == "accounts":
            account_id = parts[1]
            self._send_json(200, _get_or_create(account_id))
        elif len(parts) == 3 and parts[0] == "accounts" and parts[2] == "exposure":
            exp = trace.get_account_exposure_query(parts[1])
            if exp:
                self._send_json(200, exp.to_dict() if hasattr(exp, "to_dict") else exp)
            else:
                self._send_json(200, {"account_id": parts[1], "legitimate_balance": 20000.0, "suspicious_exposure": 0.0, "total_balance": 20000.0})
        elif len(parts) == 3 and parts[0] == "accounts" and parts[2] == "convergent":
            conv = trace.get_convergent_chains(parts[1])
            self._send_json(200, conv.to_dict() if hasattr(conv, "to_dict") else conv)
        elif len(parts) == 3 and parts[0] == "accounts" and parts[2] in ("terminal-history", "terminal_history"):
            hist = geo.get_account_terminal_history(parts[1])
            self._send_json(200, hist)
        elif parts in (["terminal", "blocks"], ["terminals", "blocks"]):
            self._send_json(200, {"blocks": _TERMINAL_BLOCKS})
        elif len(parts) == 3 and parts[0] in ("terminal", "terminals") and parts[2] == "blocks":
            tid = parts[1]
            self._send_json(200, {"terminal_id": tid, "blocks": _TERMINAL_BLOCKS.get(tid, [])})
        elif parts in (["terminal", "attempts"], ["terminals", "attempts"]):
            attempts = store.get_withdrawal_attempts(limit=100)
            self._send_json(200, {"attempts": attempts})
        elif len(parts) == 3 and parts[0] in ("terminals", "terminal") and parts[2] == "nearby":
            nearby = geo.find_nearby_terminals(parts[1], radius_km=5.0, limit=5)
            self._send_json(200, {"terminal_id": parts[1], "nearby_terminals": nearby})
        elif parts == ["confirmations"]:
            ctrl.check_timeouts()
            confs = store.recent_confirmations(limit=100)
            self._send_json(200, {"confirmations": [c.to_dict() if hasattr(c, "to_dict") else c for c in confs]})
        elif len(parts) == 2 and parts[0] == "confirmations":
            ctrl.check_timeouts()
            conf = store.get_confirmation(parts[1])
            if conf:
                self._send_json(200, conf.to_dict() if hasattr(conf, "to_dict") else conf)
            else:
                self._send_json(404, {"error": "confirmation not found"})
        elif parts == ["recovery-workflows"] or parts == ["recovery_workflows"]:
            workflows = store.recent_recovery_workflows(limit=100) if hasattr(store, "recent_recovery_workflows") else []
            self._send_json(200, {"recovery_workflows": [w.to_dict() if hasattr(w, "to_dict") else w for w in workflows]})
        elif len(parts) == 2 and parts[0] in ("recovery-workflows", "recovery_workflows"):
            rec = store.get_recovery_workflow(parts[1]) or store.get_recovery_workflow_by_case(parts[1])
            if rec:
                self._send_json(200, rec.to_dict() if hasattr(rec, "to_dict") else rec)
            else:
                self._send_json(404, {"error": "recovery workflow not found"})
        elif parts == ["chains"]:
            chains = store.recent_chains(limit=100)
            self._send_json(200, {"chains": [c.to_dict() if hasattr(c, "to_dict") else c for c in chains]})
        elif len(parts) == 2 and parts[0] == "chains":
            chain = trace.get_transaction_chain(parts[1])
            if chain:
                self._send_json(200, chain.to_dict() if hasattr(chain, "to_dict") else chain)
            else:
                self._send_json(404, {"error": "chain not found"})
        elif len(parts) == 4 and parts[0] == "chains" and parts[1] == "account" and parts[3] == "exposure":
            exp = trace.get_account_exposure_query(parts[2])
            if exp:
                self._send_json(200, exp.to_dict() if hasattr(exp, "to_dict") else exp)
            else:
                self._send_json(200, {"account_id": parts[2], "legitimate_balance": 20000.0, "suspicious_exposure": 0.0, "total_balance": 20000.0})
        elif len(parts) == 4 and parts[0] == "chains" and parts[1] == "account" and parts[3] == "convergent":
            conv = trace.get_convergent_chains(parts[2])
            self._send_json(200, conv.to_dict() if hasattr(conv, "to_dict") else conv)
        elif parts in (["recovery-cases"], ["recovery_cases"]):
            cases = store.recent_recovery_cases(limit=100)
            self._send_json(200, {"recovery_cases": [c.to_dict() if hasattr(c, "to_dict") else c for c in cases]})
        elif len(parts) == 2 and parts[0] in ("recovery-cases", "recovery_cases"):
            case_rec = trace.get_recovery_case_query(parts[1])
            if case_rec:
                self._send_json(200, case_rec.to_dict() if hasattr(case_rec, "to_dict") else case_rec)
            else:
                self._send_json(404, {"error": "recovery case not found"})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] == "withdrawals":
            withdrawals = geo.get_case_withdrawals(parts[1])
            self._send_json(200, {"case_id": parts[1], "withdrawal_attempts": withdrawals})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] == "locations":
            locations = geo.get_case_location_history(parts[1])
            self._send_json(200, {"case_id": parts[1], "locations": [loc.to_dict() for loc in locations]})
        elif parts == ["cases"]:
            orch = _get_orchestrator()
            st = self.headers.get("X-Filter-Status")
            pr = self.headers.get("X-Filter-Priority")
            acc = self.headers.get("X-Filter-Account")
            cases = orch.list_cases(limit=100, state=st, priority=pr, account_id=acc)
            self._send_json(200, {"cases": cases})
        elif len(parts) == 2 and parts[0] == "cases":
            orch = _get_orchestrator()
            c_details = orch.get_case_details(parts[1])
            if c_details:
                self._send_json(200, c_details)
            else:
                self._send_json(404, {"error": "case not found"})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] == "timeline":
            orch = _get_orchestrator()
            tl = orch.get_case_timeline(parts[1])
            self._send_json(200, {"case_id": parts[1], "timeline_events": tl})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] == "evidence":
            orch = _get_orchestrator()
            c_details = orch.get_case_details(parts[1])
            if c_details:
                self._send_json(200, {
                    "case_id": parts[1],
                    "evidence": c_details.get("evidence", []),
                    "money_trail": c_details.get("money_trail", []),
                    "predicted_terminals": c_details.get("predicted_terminals", []),
                    "withdrawal_attempts": c_details.get("withdrawal_attempts", []),
                    "complaint_id": c_details.get("complaint_id"),
                    "fir_number": c_details.get("fir_number"),
                })
            else:
                self._send_json(404, {"error": "case not found"})
        elif parts in (["police"], ["police-app"], ["police", "ui"]):
            self._send_html(200, POLICE_APP_HTML)
        elif parts in (["police-alerts"], ["police_alerts"]):
            pol = _get_police_manager()
            st = self.headers.get("X-Filter-Status")
            pr = self.headers.get("X-Filter-Priority")
            alerts = pol.list_police_alerts(limit=100, status=st, priority=pr)
            self._send_json(200, {"police_alerts": alerts})
        elif len(parts) == 2 and parts[0] in ("police-alerts", "police_alerts"):
            pol = _get_police_manager()
            alert = pol.get_police_alert(parts[1])
            if alert:
                self._send_json(200, alert)
            else:
                self._send_json(404, {"error": "police alert not found"})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] in ("police-alert", "police_alert"):
            pol = _get_police_manager()
            alert = pol.store.get_police_alert_by_case(parts[1])
            if alert:
                self._send_json(200, alert)
            else:
                self._send_json(404, {"error": "police alert not found for case"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        body = self._read_body()
        ctrl = _get_control_manager()
        trace = _get_trace_engine()
        geo = _get_geo_intel()

        # Account actions: freeze, hold, selective_hold, notify, unfreeze
        if len(parts) == 3 and parts[0] == "accounts" and parts[2] in {"freeze", "hold", "selective_hold", "selective-hold", "notify", "unfreeze"}:
            account_id, action = parts[1], parts[2].replace("-", "_")
            result = _record_action(account_id, action, body)
            self._send_json(200, {"account_id": account_id, "action": action, "result": result})
        elif parts == ["terminal", "block"] or (len(parts) == 3 and parts[0] in ("terminal", "terminals") and parts[2] == "block"):
            if len(parts) == 3:
                body["terminal_id"] = parts[1]
            res = _record_terminal_block(body)
            self._send_json(200, {"status": "SUCCESS", "block": res})
        elif parts == ["terminal", "attempt"] or (len(parts) == 3 and parts[0] in ("terminal", "terminals") and parts[2] == "attempt"):
            tid = body.get("terminal_id", parts[1] if len(parts) == 3 else "UNKNOWN")
            acc_id = body.get("account_id", "UNKNOWN")
            amt = float(body.get("amount_inr", body.get("amount", 0.0)))
            att_id = body.get("attempt_id", f"ATT-{hashlib.md5(f'{tid}{acc_id}{amt}'.encode()).hexdigest()[:8]}")

            attempt_event = geo.process_withdrawal_attempt(
                attempt_id=att_id,
                account_id=acc_id,
                terminal_id=tid,
                amount_inr=amt,
                timestamp=body.get("timestamp"),
                latitude=body.get("latitude"),
                longitude=body.get("longitude"),
                payment_channel=body.get("payment_channel", body.get("channel", "ATM")),
                case_id=body.get("case_id"),
                existing_balance=float(body.get("existing_balance", 20000.0)),
            )
            self._send_json(200, {"status": "SUCCESS", "attempt": attempt_event.to_dict()})
        elif parts == ["confirmations", "request"]:
            rec = ctrl.request_confirmation(
                transaction_id=str(body.get("transaction_id", "")),
                sender_id=str(body.get("sender_id", "")),
                beneficiary_id=str(body.get("beneficiary_id", "")),
                amount=float(body.get("amount", 0.0)),
                reason=body.get("reason", "High-value/anomalous transfer confirmation requested"),
                timeout_seconds=int(body.get("timeout_seconds", 300)),
                case_id=body.get("case_id"),
                metadata=body.get("metadata"),
            )
            self._send_json(200, {"status": "SUCCESS", "confirmation": rec.to_dict()})
        elif len(parts) == 3 and parts[0] == "confirmations" and parts[2] == "respond":
            conf_id = parts[1]
            status_val = body.get("status", "")
            notes = body.get("notes", "")
            responder_id = body.get("responder_id")
            try:
                rec = ctrl.submit_confirmation_response(
                    confirmation_id=conf_id,
                    response_status=status_val,
                    notes=notes,
                    responder_id=responder_id,
                )
                self._send_json(200, {"status": "SUCCESS", "confirmation": rec.to_dict() if hasattr(rec, "to_dict") else rec})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        elif parts in (["transaction-control", "evaluate"], ["transaction_control", "evaluate"]):
            decision = ctrl.evaluate_transaction_control(
                transaction_id=str(body.get("transaction_id", "TX-EVAL")),
                from_account=str(body.get("from_account", "")),
                to_account=str(body.get("to_account", "")),
                amount=float(body.get("amount", 0.0)),
                channel_or_type=str(body.get("channel", body.get("channel_or_type", "UPI"))),
                timestamp=body.get("timestamp"),
                existing_balance=float(body.get("existing_balance", 20000.0)),
            )
            self._send_json(200, {"status": "SUCCESS", "decision": decision.to_dict()})
        elif parts in (["chains", "track-descendant"], ["chains", "track_descendant"]):
            updated = trace.track_descendant_transaction(
                parent_transaction_id=body.get("parent_transaction_id"),
                child_transaction_id=str(body.get("child_transaction_id", "")),
                from_account_id=str(body.get("from_account_id", "")),
                to_account_id=str(body.get("to_account_id", "")),
                amount_inr=float(body.get("amount_inr", 0.0)),
                payment_channel=str(body.get("payment_channel", "UPI")),
                timestamp=body.get("timestamp"),
                is_cashout=bool(body.get("is_cashout", False)),
                terminal_id=body.get("terminal_id"),
            )
            self._send_json(200, {"status": "SUCCESS", "chains_updated": [c.to_dict() for c in updated]})
        elif len(parts) == 3 and parts[0] in ("recovery-cases", "recovery_cases") and parts[2] == "status":
            case_id = parts[1]
            new_status = body.get("status", "")
            rec_amt = float(body.get("recovered_amount", 0.0))
            notes = body.get("notes", "")
            try:
                updated_case = trace.update_recovery_status(
                    case_id=case_id,
                    new_status=new_status,
                    recovered_amount=rec_amt,
                    action_note=notes,
                )
                self._send_json(200, {"status": "SUCCESS", "recovery_case": updated_case.to_dict()})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] == "escalate":
            case_id = parts[1]
            reason = body.get("reason", "")
            role = body.get("role", "BANK_OFFICIAL")
            orch = _get_orchestrator()
            try:
                rec = orch.escalate_case(case_id=case_id, reason=reason, actor_role=role)
                self._send_json(200, {"status": "SUCCESS", "case": rec.to_dict()})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] == "resolve":
            case_id = parts[1]
            reason = body.get("reason", "Resolved")
            actor_id = body.get("actor_id")
            orch = _get_orchestrator()
            try:
                rec = orch.resolve_case(case_id=case_id, reason=reason, actor_id=actor_id)
                self._send_json(200, {"status": "SUCCESS", "case": rec.to_dict()})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] == "dismiss":
            case_id = parts[1]
            reason = body.get("reason", "False Positive")
            actor_id = body.get("actor_id")
            orch = _get_orchestrator()
            try:
                rec = orch.dismiss_case(case_id=case_id, reason=reason, actor_id=actor_id)
                self._send_json(200, {"status": "SUCCESS", "case": rec.to_dict()})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] in ("complaint", "fir"):
            case_id = parts[1]
            c_id = body.get("complaint_id", body.get("complaint_number", "NCRP-REQ"))
            fir_num = body.get("fir_number")
            victim_acc = body.get("victim_account")
            rep_loss = float(body.get("reported_loss", 0.0)) if body.get("reported_loss") else None
            orch = _get_orchestrator()
            try:
                rec = orch.attach_complaint_fir(
                    case_id=case_id,
                    complaint_id=c_id,
                    fir_number=fir_num,
                    victim_account=victim_acc,
                    reported_loss=rep_loss,
                )
                self._send_json(200, {"status": "SUCCESS", "case": rec.to_dict()})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        elif len(parts) == 3 and parts[0] == "cases" and parts[2] in ("police-alert", "police_alert"):
            case_id = parts[1]
            caller_role = self.headers.get("X-User-Role", body.get("role", "BANK_OFFICIAL"))
            source = body.get("source", "CyberShield Bank Official")
            orch = _get_orchestrator()
            try:
                res = orch.trigger_police_alert(case_id=case_id, actor_role=caller_role, source=source)
                self._send_json(200, res)
            except PermissionError as e:
                self._send_json(403, {"error": str(e)})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        elif len(parts) == 3 and parts[0] in ("police-alerts", "police_alerts") and parts[2] == "acknowledge":
            alert_id = parts[1]
            caller_role = self.headers.get("X-User-Role", body.get("role", "POLICE_OFFICER"))
            officer_id = body.get("officer_id", "DUTY-OFFICER-01")
            notes = body.get("notes", "")
            pol = _get_police_manager()
            try:
                rec = pol.acknowledge_police_alert(police_alert_id=alert_id, caller_role=caller_role, officer_id=officer_id, notes=notes)
                self._send_json(200, {"status": "SUCCESS", "police_alert": rec.to_dict()})
            except PermissionError as e:
                self._send_json(403, {"error": str(e)})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        elif len(parts) == 3 and parts[0] in ("police-alerts", "police_alerts") and parts[2] == "status":
            alert_id = parts[1]
            caller_role = self.headers.get("X-User-Role", body.get("role", "POLICE_OFFICER"))
            officer_id = body.get("officer_id", "DUTY-OFFICER-01")
            new_status = body.get("status", "")
            notes = body.get("notes", "")
            pol = _get_police_manager()
            try:
                rec = pol.update_investigation_status(police_alert_id=alert_id, new_status=new_status, caller_role=caller_role, officer_id=officer_id, notes=notes)
                self._send_json(200, {"status": "SUCCESS", "police_alert": rec.to_dict()})
            except PermissionError as e:
                self._send_json(403, {"error": str(e)})
            except KeyError as e:
                self._send_json(404, {"error": str(e)})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        else:
            self._send_json(404, {"error": "not found"})


def run(port: int = 8001) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Mock Bank & Terminal API listening on http://localhost:{port}  "
          f"(banks simulated: {', '.join(BANKS)})")
    server.serve_forever()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8001)
