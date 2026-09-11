"""mock_services/bank_api/server.py — a fake bank, for the demo only.

Deliberately built on the Python standard library only (http.server) — zero
pip installs required, which matters when you're wiring this together the
night before a demo. Simulates 3 named banks (accounts are deterministically
assigned to one via hash) with in-memory account status: ACTIVE, HOLD,
FROZEN.

This is what "automatic bank action" means in this prototype: a real,
callable HTTP API that the detection pipeline can hit automatically — not a
slide claiming integration with an actual bank's core banking system, which
no hackathon team can get access to.

Run:  python -m mock_services.bank_api.server [port]   (default port 8001)

Endpoints:
  POST /accounts/{account_id}/freeze   {"reason": "...", "complaint_id": "...", "confidence": 0.9}
  POST /accounts/{account_id}/hold     (same body)
  POST /accounts/{account_id}/notify   (same body)  -- soft alert, no status change
  POST /accounts/{account_id}/unfreeze
  GET  /accounts/{account_id}          -- current status + action history
  GET  /accounts                       -- every account this server has seen
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BANKS = ["HDFC-SIM", "ICICI-SIM", "SBI-SIM"]

# account_id -> {"bank": str, "status": str, "history": [ {...} ]}
_ACCOUNTS: dict = {}


def _bank_for(account_id: str) -> str:
    h = int(hashlib.sha256(account_id.encode()).hexdigest(), 16)
    return BANKS[h % len(BANKS)]


def _get_or_create(account_id: str) -> dict:
    if account_id not in _ACCOUNTS:
        _ACCOUNTS[account_id] = {"bank": _bank_for(account_id), "status": "ACTIVE", "history": []}
    return _ACCOUNTS[account_id]


def _record_action(account_id: str, action: str, body: dict) -> dict:
    acc = _get_or_create(account_id)
    entry = {
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": body.get("reason", ""),
        "complaint_id": body.get("complaint_id", ""),
        "confidence": body.get("confidence"),
    }
    acc["history"].append(entry)
    if action == "freeze":
        acc["status"] = "FROZEN"
    elif action == "hold":
        acc["status"] = "HOLD" if acc["status"] != "FROZEN" else acc["status"]
    elif action == "unfreeze":
        acc["status"] = "ACTIVE"
    print(f"[BANK:{acc['bank']}] {action.upper()} on {account_id} "
          f"(complaint {entry['complaint_id']}, reason: {entry['reason']})")
    return acc


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

    def log_message(self, fmt, *args):  # quieter default logging
        pass

    def do_GET(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if parts == ["accounts"]:
            self._send_json(200, {"accounts": _ACCOUNTS})
        elif len(parts) == 2 and parts[0] == "accounts":
            account_id = parts[1]
            self._send_json(200, _get_or_create(account_id))
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 3 and parts[0] == "accounts" and parts[2] in {"freeze", "hold", "notify", "unfreeze"}:
            account_id, action = parts[1], parts[2]
            body = self._read_body()
            result = _record_action(account_id, action, body)
            self._send_json(200, {"account_id": account_id, "action": action, "result": result})
        else:
            self._send_json(404, {"error": "not found"})


def run(port: int = 8001) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Mock Bank API listening on http://localhost:{port}  "
          f"(banks simulated: {', '.join(BANKS)})")
    server.serve_forever()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8001)
