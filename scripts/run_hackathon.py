"""Start mock bank + NCRP + CyberShield API for the hackathon demo."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mock_services.bank_api.server import run as run_bank
from mock_services.ncrp_i4c_api.server import run as run_ncrp

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> None:
    threading.Thread(target=run_bank, kwargs={"port": 8001}, daemon=True).start()
    threading.Thread(target=run_ncrp, kwargs={"port": 8002}, daemon=True).start()
    print("Mock Bank API   http://127.0.0.1:8001")
    print("Mock NCRP/I4C   http://127.0.0.1:8002")
    print("CyberShield API http://127.0.0.1:5003")
    from api.server import run as run_api
    run_api(5003)


if __name__ == "__main__":
    main()
