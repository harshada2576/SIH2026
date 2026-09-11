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
        if len(parts) == 3 and parts[0] == "cases" and parts[2] == "heatmap":
            case_id = parts[1]
            case = ENGINE.get(case_id)
            if not case:
                self._send(404, {"error": "case not found"})
                return
            event_type = (q.get("event_type") or [None])[0]
            city = (q.get("city") or [None])[0]
            start_time = (q.get("start_time") or [None])[0]
            end_time = (q.get("end_time") or [None])[0]
            aggregate_str = (q.get("aggregate") or ["true"])[0]
            aggregate = (aggregate_str.lower() != "false")
            data = ENGINE.get_heatmap_points(
                case_id=case_id,
                event_type=event_type,
                city=city,
                start_time=start_time,
                end_time=end_time,
                aggregate=aggregate,
            )
            self._send(200, data)
            return
        if parts == ["heatmap"]:
            event_type = (q.get("event_type") or [None])[0]
            city = (q.get("city") or [None])[0]
            start_time = (q.get("start_time") or [None])[0]
            end_time = (q.get("end_time") or [None])[0]
            case_id = (q.get("case_id") or [None])[0]
            aggregate_str = (q.get("aggregate") or ["true"])[0]
            aggregate = (aggregate_str.lower() != "false")
            data = ENGINE.get_heatmap_points(
                case_id=case_id,
                event_type=event_type,
                city=city,
                start_time=start_time,
                end_time=end_time,
                aggregate=aggregate,
            )
            self._send(200, data)
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
