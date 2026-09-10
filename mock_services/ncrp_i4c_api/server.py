"""mock_services/ncrp_i4c_api/server.py — a fake NCRP/I4C intake endpoint, for the demo only.

No hackathon team can get real access to NCRP/I4C systems, and claiming to
have "integrated" with them would hurt credibility with judges who know that.
What this gives you instead: a real, callable API that plays the same *role*
(LEA notification + case-number acknowledgement) so the pipeline's
interoperability step is genuinely exercised end-to-end, with an honest label.

Run: python -m mock_services.ncrp_i4c_api.server [port]   (default port 8002)

Endpoints:
  POST /alerts   {"complaint_id": ..., "flagged_account_id": ..., "risk_score": ..., "evidence": [...]}
       -> {"case_number": "I4C-2026-000042", "status": "ACKNOWLEDGED", "assigned_unit": "..."}
  GET  /alerts   -> every alert this server has received
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

UNITS = ["Cyber Cell - District Alpha", "Cyber Cell - District Bravo", "State Cyber Wing"]

_ALERTS: list = []
_COMPLAINTS: list = []
_DISPATCHES: list = []
_counter = [0]


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
        if parts == ["alerts"]:
            self._send_json(200, {"alerts": _ALERTS})
        elif parts == ["complaints"]:
            self._send_json(200, {"complaints": _COMPLAINTS})
        elif parts == ["dispatches"]:
            self._send_json(200, {"dispatches": _DISPATCHES})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        body = self._read_body()

        if parts == ["alerts"]:
            _counter[0] += 1
            case_number = f"I4C-{datetime.now(timezone.utc).year}-{_counter[0]:06d}"
            unit = UNITS[_counter[0] % len(UNITS)]
            is_pre = body.get("pre_complaint", True)
            status = "PRE_COMPLAINT_ACKNOWLEDGED" if is_pre else "POST_COMPLAINT_ESCALATED"
            record = {
                "case_number": case_number,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "assigned_unit": unit,
                "alert": body,
            }
            _ALERTS.append(record)
            print(f"[NCRP/I4C] Alert {body.get('complaint_id', body.get('case_id', '?'))} acknowledged as "
                  f"{case_number} ({status}), assigned to {unit}")
            self._send_json(200, record)
        elif parts == ["complaints"]:
            _counter[0] += 1
            ncrp_id = body.get("complaint_id", f"NCRP-{datetime.now(timezone.utc).year}-{990000 + _counter[0]}")
            unit = body.get("assigned_unit", UNITS[_counter[0] % len(UNITS)])
            record = {
                "ncrp_id": ncrp_id,
                "case_number": f"I4C-{datetime.now(timezone.utc).year}-{_counter[0]:06d}",
                "victim_account": body.get("victim_account", "ACC-VICTIM"),
                "reported_loss": body.get("reported_loss", "₹1,00,000"),
                "associated_case_id": body.get("case_id"),
                "status": "COMPLAINT_ESCALATED",
                "assigned_unit": unit,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _COMPLAINTS.append(record)
            print(f"[NCRP/1930] Formal Victim Complaint Filed: {ncrp_id} | Loss: {record['reported_loss']} -> Escalated to {unit}")
            self._send_json(200, record)
        elif parts == ["dispatches"]:
            dispatch_id = f"DISP-{len(_DISPATCHES) + 1:04d}"
            record = {
                "dispatch_id": dispatch_id,
                "ncrp_id": body.get("ncrp_id", ""),
                "case_id": body.get("case_id", ""),
                "terminal_id": body.get("terminal_id", ""),
                "target_unit": body.get("target_unit", "Sector 20 Police Patrol Unit"),
                "action": body.get("action", "FIELD_INTERCEPTION_DISPATCH"),
                "status": "EN_ROUTE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            _DISPATCHES.append(record)
            print(f"[LEA_DISPATCH] Unit {record['target_unit']} DISPATCHED to Terminal {record['terminal_id']} for Case {record['case_id']}")
            self._send_json(200, record)
        else:
            self._send_json(404, {"error": "not found"})


def run(port: int = 8002) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Mock NCRP/I4C API listening on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8002)

