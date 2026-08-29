"""Loads static ATM/AEPS/POS reference data once, into shared/terminals.json.

Run:  python scripts/seed_terminals.py   (only needs stdlib)
The scorer reads this file at detection time; the dashboard plots it on the map.
"""
from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.schemas import TerminalNode

# Prototype reference geography: three fake districts, lat/lon around NCR.
DISTRICTS = [
    {"district_pincode": "110001", "name": "Central Delhi", "lat": 28.63, "lon": 77.22},
    {"district_pincode": "201301", "name": "Noida",         "lat": 28.57, "lon": 77.32},
    {"district_pincode": "302001", "name": "Jaipur",        "lat": 26.91, "lon": 75.79},
]

BANKS = ["SBI", "PNB", "HDFC", "ICICI"]
AGENTS = ["BCR"]

random.seed(20260828)  # deterministic output so the scorer demo is reproducible


def _jitter(base: float, spread: float = 0.02) -> float:
    return round(base + random.uniform(-spread, spread), 5)


def build_terminals(per_district: int = 10) -> list[TerminalNode]:
    """Generate ~30 fictional terminals spread over the fake districts."""
    terminals: list[TerminalNode] = []
    seq = 0
    for d in DISTRICTS:
        for i in range(per_district):
            kind = i % 3
            if kind == 0:
                ttype, prefix = "ATM_KIOSK", f"ATM-{random.choice(BANKS)}-{d['name'][:2]}"
            elif kind == 1:
                ttype, prefix = "AEPS_MICRO_ATM", f"AEPS-{random.choice(AGENTS)}"
            else:
                ttype, prefix = "POS", f"POS-{random.choice(BANKS)}"
            seq += 1
            terminals.append(TerminalNode(
                terminal_id=f"{prefix}-{seq:03d}",
                terminal_type=ttype,
                latitude=_jitter(d["lat"]),
                longitude=_jitter(d["lon"]),
                district_pincode=d["district_pincode"],
            ))
    return terminals


def main() -> None:
    """Write terminals.json next to shared/schemas.py (i.e. shared/terminals.json)."""
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "shared", "terminals.json")
    rows = [{"terminal_id": t.terminal_id, "terminal_type": t.terminal_type,
             "latitude": t.latitude, "longitude": t.longitude,
             "district_pincode": t.district_pincode} for t in build_terminals()]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    print(f"wrote {len(rows)} terminals -> {os.path.normpath(out)}")


if __name__ == "__main__":
    main()