#!/usr/bin/env python3
"""
scripts/live_demo/run_background.py — Background Daemon Manager for Normal Traffic
SIH26184 — Predictive Cash Egress Interception

Commands:
  start   : Launches normal traffic generator in the background (PID tracked in .normal_traffic.pid)
  stop    : Sends SIGTERM to cleanly stop the background generator
  status  : Checks if background generator is currently running
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PID_FILE = REPO_ROOT / ".normal_traffic.pid"
LOG_FILE = REPO_ROOT / "data" / "output" / "normal_traffic.log"

def start(rate: float, api_url: str):
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            print(f"[!] Background traffic is ALREADY RUNNING (PID: {pid}).")
            print(f"    View logs: tail -f {LOG_FILE}")
            return
        except OSError:
            PID_FILE.unlink(missing_ok=True)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    python_bin = sys.executable
    script_path = REPO_ROOT / "scripts" / "live_demo" / "normal_traffic.py"

    cmd = [
        python_bin,
        str(script_path),
        "--continuous",
        "--rate", str(rate),
        "--api-url", api_url,
    ]

    log_fd = open(LOG_FILE, "a")
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=log_fd,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"[+] Started normal background traffic stream (PID: {proc.pid}, Rate: {rate} tx/s)")
    print(f"    Log output: {LOG_FILE}")
    print(f"    To monitor: tail -f {LOG_FILE}")
    print(f"    To stop:    python scripts/live_demo/run_background.py stop")

def stop():
    if not PID_FILE.exists():
        print("[-] No active background traffic process found (PID file missing).")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        print(f"[*] Stopping background traffic process (PID: {pid})...")
        os.kill(pid, signal.SIGINT)
        time.sleep(1.0)
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        PID_FILE.unlink(missing_ok=True)
        print("[+] Background traffic generator stopped successfully.")
    except Exception as e:
        print(f"[!] Error stopping process: {e}")
        PID_FILE.unlink(missing_ok=True)

def status():
    if not PID_FILE.exists():
        print("[-] Background normal traffic: NOT RUNNING")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        print(f"[+] Background normal traffic: RUNNING (PID: {pid})")
        print(f"    Log file: {LOG_FILE}")
    except OSError:
        print("[-] Background normal traffic: NOT RUNNING (stale PID file cleaned up)")
        PID_FILE.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description="CyberShield Background Traffic Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_p = subparsers.add_parser("start", help="Start background traffic generator")
    start_p.add_argument("--rate", type=float, default=5.0, help="Transactions per second (default 5.0)")
    start_p.add_argument("--api-url", default="http://127.0.0.1:5003", help="Backend API base URL")

    subparsers.add_parser("stop", help="Stop background traffic generator")
    subparsers.add_parser("status", help="Check status of background traffic generator")

    args = parser.parse_args()
    if args.command == "start":
        start(args.rate, args.api_url)
    elif args.command == "stop":
        stop()
    elif args.command == "status":
        status()

if __name__ == "__main__":
    main()
