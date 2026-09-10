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
  POST /terminal/attempt               -- log cashout attempt
  GET  /terminal/attempts              -- list cashout attempts
  POST /confirmations/request          -- create PENDING_CONFIRMATION
  POST /confirmations/{id}/respond     -- respond CONFIRMED_LEGITIMATE or CONFIRMED_FRAUD
  GET  /confirmations/{id}             -- get confirmation record
  GET  /confirmations                  -- get confirmation records
  POST /transaction-control/evaluate   -- evaluate transfer or withdrawal channel control
  GET  /recovery-workflows             -- list recovery workflows
  GET  /recovery-workflows/{id}        -- get recovery workflow
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from detection.transaction_control import TransactionControlManager
from shared.persistence import Store

BANKS = ["HDFC-SIM", "ICICI-SIM", "SBI-SIM"]

# account_id -> {"bank": str, "status": str, "existing_balance": float, "held_balance": float, "available_balance": float, "history": [ {...} ]}
_ACCOUNTS: dict = {}
_TERMINAL_BLOCKS: dict = {}   # terminal_id -> [ block_reqs ]
_WITHDRAWAL_ATTEMPTS: list = [] # list of attempt logs

_STORE: Optional[Store] = None
_CONTROL_MGR: Optional[TransactionControlManager] = None


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


def _record_withdrawal_attempt(body: dict) -> dict:
    tid = str(body.get("terminal_id", "UNKNOWN"))
    acc_id = str(body.get("account_id", "UNKNOWN"))
    amount = float(body.get("amount_inr", 0.0))

    # Check if terminal or account is blocked
    has_terminal_block = any(b["status"] == "ACTIVE" for b in _TERMINAL_BLOCKS.get(tid, []))
    acc_status = _ACCOUNTS.get(acc_id, {}).get("status", "ACTIVE")
    is_blocked = has_terminal_block or acc_status in ("FROZEN", "HOLD", "PROVISIONAL_HOLD", "SELECTIVE_HOLD")

    status_str = "BLOCKED" if is_blocked else "ALLOWED"
    action_str = "BLOCK_WITHDRAWAL" if is_blocked else "ALLOW_WITHDRAWAL"
    reason = "Terminal or Account Cashout Interception Active" if is_blocked else "Clean standard withdrawal"

    record = {
        "attempt_id": body.get("attempt_id", f"ATT-{hashlib.md5(f'{tid}{acc_id}{amount}'.encode()).hexdigest()[:8]}"),
        "terminal_id": tid,
        "account_id": acc_id,
        "amount_inr": amount,
        "timestamp": body.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "status": status_str,
        "action": action_str,
        "reason": reason,
        "correlated_case_id": body.get("case_id"),
    }
    _WITHDRAWAL_ATTEMPTS.append(record)
    print(f"[ATM_SWITCH] Cashout attempt at {tid} by {acc_id} for ₹{amount:,.2f} -> {status_str} ({reason})")
    return record


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
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

        if parts == ["accounts"]:
            self._send_json(200, {"accounts": _ACCOUNTS})
        elif len(parts) == 2 and parts[0] == "accounts":
            account_id = parts[1]
            self._send_json(200, _get_or_create(account_id))
        elif parts in (["terminal", "blocks"], ["terminals", "blocks"]):
            self._send_json(200, {"blocks": _TERMINAL_BLOCKS})
        elif len(parts) == 3 and parts[0] in ("terminal", "terminals") and parts[2] == "blocks":
            tid = parts[1]
            self._send_json(200, {"terminal_id": tid, "blocks": _TERMINAL_BLOCKS.get(tid, [])})
        elif parts in (["terminal", "attempts"], ["terminals", "attempts"]):
            self._send_json(200, {"attempts": _WITHDRAWAL_ATTEMPTS})
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
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        body = self._read_body()
        ctrl = _get_control_manager()

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
            if len(parts) == 3:
                body["terminal_id"] = parts[1]
            res = _record_withdrawal_attempt(body)
            self._send_json(200, {"status": "SUCCESS", "attempt": res})
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
        else:
            self._send_json(404, {"error": "not found"})


def run(port: int = 8001) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Mock Bank & Terminal API listening on http://localhost:{port}  "
          f"(banks simulated: {', '.join(BANKS)})")
    server.serve_forever()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8001)
