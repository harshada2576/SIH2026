"""Alert dispatcher — console stub (Kafka publish is explicitly deferred).

Architecture.md has this publishing to the `risk_alerts` topic, and the
dashboard consuming it. The group brief says "ignore Kafka implementation for
now", so this stub prints the investigator-grade alert to the console instead.
Wiring the real Kafka producer + `shared.kafka_utils` into `dispatch()` is the
integration-day task (flag tracked in Memory.md).
"""
from __future__ import annotations

import sys
from typing import Optional

from shared.schemas import RiskAlert


def _ensure_utf8() -> None:
    """The alert text carries ₹ and other non-ASCII; force UTF-8 output streams."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass  # some environments disallow reconfiguration; print() still works


def dispatch(alert: RiskAlert, kafka_topic: Optional[str] = "risk_alerts") -> None:
    """Format the RiskAlert for a human investigator (and later Kafka).

    kafka_topic is accepted today so the call-site signature doesn't change when
    the Kafka producer is plugged in.
    """
    _ensure_utf8()
    line = "=" * 72
    print(line)
    print(f"  ALERT  {alert.complaint_id}   ({kafka_topic})")
    print(line)
    print(f"  RISK: {alert.risk_score:.2f} / flagged account {alert.flagged_account_id}")
    print(f"  CASH-OUT WINDOW: {alert.predicted_window_start:%Y-%m-%d %H:%M}Z "
          f"-> {alert.predicted_window_end:%H:%M}Z")
    print("\n  WHY:")
    for e in alert.evidence:
        print(f"    - {e}")
    if alert.predicted_terminals:
        print("\n  PREDICTED CASH-OUT LOCATIONS (priority, most likely first):")
        for i, t in enumerate(alert.predicted_terminals, 1):
            print(f"    #{i} {t.terminal_id:<20} {t.probability:.2f} "
                  f"({t.latitude:.4f}, {t.longitude:.4f})")
    print("\n  NOTE: priority scores are investigative hints, not calibrated "
          "probabilities and not proof of fraud. Human/authorized action only.")
    print(line)