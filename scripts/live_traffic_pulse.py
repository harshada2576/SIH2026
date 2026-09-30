#!/usr/bin/env python3
"""scripts/live_traffic_pulse.py — High-volume continuous case generator & 15-20s alert pulse.

Fills the CyberShield mobile app with rich cases across all statuses:
- Bank Review Queue (PENDING, BANK_HOLD, RELEASED)
- Police Cases (APPROVED / SENT TO POLICE, EN_ROUTE, BLOCKED)
- Dispatches continuous fresh fraud alert pulses every 15-20 seconds with WebSocket broadcasts.
"""
import time
import json
import urllib.request
import urllib.error
import random
import sys

BASE = "https://sih-render.seucra.tech"

OFFICERS_POLICE = [
    "Insp. Vikram Rathore (Delhi Cyber Command)",
    "ACP Rajesh Kumar (Mumbai Cyber LEA)",
    "SI Anita Deshmukh (Crime Branch Cell)",
    "Insp. Harpreet Singh (Special Task Force)",
    "Field Patrol Unit 42 (PCR Central Metro)"
]

OFFICERS_BANK = [
    "Vigilance Manager S. Nair (SBI Central Vigilance)",
    "Chief Risk Officer P. V. Sharma (HDFC Cyber Fraud Cell)",
    "Duty Officer M. K. Iyer (RBI Cyber Security Operations)",
    "Lead Analyst R. Sen (National Payments SOC)"
]

def post_json(path, payload):
    url = f"{BASE}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"[-] Error calling {path}: {e}")
        return None

def trigger_new_fraud_alert():
    return post_json("/demo/trigger_fraud", {})

def act_on_case(ncrp_id, action, officer):
    return post_json(f"/cases/{ncrp_id}/{action}", {"officer": officer})

def seed_rich_categories():
    print("[+] Seeding diverse case states across Bank and Police queues...")
    created_ids = []
    for i in range(6):
        res = trigger_new_fraud_alert()
        if res and "ncrpId" in res:
            created_ids.append(res["ncrpId"])
            print(f"    [+] Created live case {res['ncrpId']} -> {res.get('flaggedAccount')}")
        time.sleep(1.2)

    req = urllib.request.Request(f"{BASE}/cases?role=BANK")
    try:
        with urllib.request.urlopen(req) as r:
            all_cases = json.loads(r.read().decode("utf-8")).get("cases", [])
    except Exception:
        all_cases = []

    print(f"[+] Total active cases in backend: {len(all_cases)}")
    for i, c in enumerate(all_cases):
        cid = c["ncrpId"]
        if i % 4 == 0:
            act_on_case(cid, "escalate", random.choice(OFFICERS_POLICE))
            act_on_case(cid, "simulate_withdraw", "PCR Van Sector 18")
            print(f"    [*] {cid} -> SENT TO POLICE & WITHDRAWAL BLOCKED")
        elif i % 4 == 1:
            act_on_case(cid, "hold", random.choice(OFFICERS_BANK))
            print(f"    [*] {cid} -> PROVISIONAL BANK HOLD")
        elif i % 4 == 2:
            act_on_case(cid, "hold", random.choice(OFFICERS_BANK))
            act_on_case(cid, "release", random.choice(OFFICERS_BANK))
            print(f"    [*] {cid} -> RELEASED / RESOLVED")
        else:
            print(f"    [*] {cid} -> PENDING REVIEW")

def loop_pulse(interval_sec=18):
    print(f"\n[+] Starting continuous live pulse every {interval_sec}s...")
    print("[+] Keep your phone recording active! New incoming alerts and toasts will trigger continuously.")
    pulse_count = 0
    try:
        while True:
            pulse_count += 1
            print(f"\n[PULSE #{pulse_count}] Generating live high-priority fraud ingress & WebSocket toast...")
            res = trigger_new_fraud_alert()
            if res and "ncrpId" in res:
                cid = res["ncrpId"]
                amt = res.get("case", {}).get("reportedLoss", "₹1,25,000")
                term = res.get("case", {}).get("targetTerminal", {}).get("id", "ATM-TARGET")
                print(f"    [>>> TOAST SENT TO PHONE] {cid} | {amt} | Target: {term}")

                if pulse_count % 3 == 0:
                    act_on_case(cid, "escalate", random.choice(OFFICERS_POLICE))
                    print(f"    [>>> POLICE DISPATCH] Forwarded {cid} to Police Field Unit")
                elif pulse_count % 3 == 1:
                    act_on_case(cid, "hold", random.choice(OFFICERS_BANK))
                    print(f"    [>>> BANK HOLD] Differential Hold applied on {cid}")

            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\n[!] Stopped live pulse.")

if __name__ == "__main__":
    seed_rich_categories()
    if "--no-loop" not in sys.argv:
        loop_pulse(interval_sec=18)
