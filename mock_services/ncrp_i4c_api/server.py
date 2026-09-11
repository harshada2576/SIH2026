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
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if parts == ["alerts"]:
            body = self._read_body()
            _counter[0] += 1
            case_number = f"I4C-{datetime.now(timezone.utc).year}-{_counter[0]:06d}"
            unit = UNITS[_counter[0] % len(UNITS)]
            record = {
                "case_number": case_number,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "status": "ACKNOWLEDGED",
                "assigned_unit": unit,
                "alert": body,
            }
            _ALERTS.append(record)
            print(f"[NCRP/I4C] Alert {body.get('complaint_id', '?')} acknowledged as "
                  f"{case_number}, assigned to {unit}")
            self._send_json(200, record)
        else:
            self._send_json(404, {"error": "not found"})


def run(port: int = 8002) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Mock NCRP/I4C API listening on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8002)
