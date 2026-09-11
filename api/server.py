"""REST API for the CyberShield Android app. Stdlib only — no extra pip."""
from __future__ import annotations

import json
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from api.engine import CaseEngine

ENGINE = CaseEngine()


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[api] " + (fmt % args) + "\n")

    def _send(self, code: int, payload) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        q = parse_qs(parsed.query)
        if parts == ["health"]:
            self._send(200, {
                "ok": True,
                "cases": len(ENGINE.cases),
                "terminals": len(ENGINE.terminals),
                "lan_ip": _lan_ip(),
            })
            return
        if parts == ["cases"]:
            role = (q.get("role") or ["BANK"])[0]
            self._send(200, {"cases": ENGINE.list_cases(role)})
            return
        if len(parts) == 2 and parts[0] == "cases":
            case = ENGINE.get(parts[1])
            if not case:
                self._send(404, {"error": "case not found"})
                return
            self._send(200, case)
            return
        if len(parts) == 3 and parts[0] == "cases" and parts[2] == "notifications":
            ncrp_id = parts[1]
            case = ENGINE.get(ncrp_id)
            if not case:
                self._send(404, {"error": "case not found"})
                return
            notifs = ENGINE.notification_service.get_case_notifications(ncrp_id)
            summary = ENGINE.notification_service.get_case_notification_summary(ncrp_id)
            self._send(200, {
                "case_id": ncrp_id,
                "summary": summary,
                "notifications": notifs,
            })
            return
        if parts == ["terminals"]:
            self._send(200, {"terminals": ENGINE.terminal_markers()})
            return
        if parts == ["audit"]:
            self._send(200, {"audit": ENGINE.audit})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 3 and parts[0] == "cases":
            ncrp_id, action = parts[1], parts[2]
            body = self._read_json()
            if action == "notify":
                case = ENGINE.get(ncrp_id)
                if not case:
                    self._send(404, {"error": "case not found"})
                    return
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
                self._send(200, {
                    "ok": True,
                    "case_id": ncrp_id,
                    "dispatched_count": len(results),
                    "notifications": [r.to_dict() for r in results],
                })
                return

            officer = body.get("officer") or "Duty officer"
            case = ENGINE.act(ncrp_id, action, officer)
            if case is None:
                self._send(404, {"error": "case not found"})
                return
            self._send(200, case)
            return
        self._send(404, {"error": "not found"})


def run(port: int = 8080) -> None:
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    ip = _lan_ip()
    print(f"CyberShield API  http://127.0.0.1:{port}")
    print(f"Phone on same Wi-Fi: set api_base_url to http://{ip}:{port}")
    print(f"Emulator: http://10.0.2.2:{port}")
    print(f"Loaded {len(ENGINE.cases)} investigation cases from CSV + detection engine.")
    httpd.serve_forever()


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8080)
