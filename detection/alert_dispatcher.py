"""Alert dispatcher — console output (investigator-grade) PLUS Phase 2 wiring:
persistence (shared/persistence.py), tiered automated response
(detection/auto_intervention.py), and a signed, tamper-evident audit trail
(audit/blockchain_lite.py). Kafka publish to the `risk_alerts` topic is still
the integration-day task tracked in Memory.md — dispatch() accepts
`kafka_topic` today so that call sites don't need to change when it's wired.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.schemas import RiskAlert

log = logging.getLogger("alert_dispatcher")


def _ensure_utf8() -> None:
    """The alert text carries ₹ and other non-ASCII; force UTF-8 output streams."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass  # some environments disallow reconfiguration; print() still works


def dispatch(alert: RiskAlert, kafka_topic: Optional[str] = "risk_alerts",
             band: Optional[str] = None, auto_act: bool = True) -> None:
    """Format the RiskAlert for a human investigator, persist it, and (if
    `auto_act`) run the tiered automated response + write a signed audit entry.

    kafka_topic is accepted today so the call-site signature doesn't change when
    the Kafka producer is plugged in.
    band: risk band (LOW/MEDIUM/HIGH/CRITICAL) if the caller already computed
    one (detection.scorer.risk_band); recomputed from risk_score if omitted.
    """
    _ensure_utf8()
    line = "=" * 72
    print(line)
    print(f"  ALERT  {alert.complaint_id}   ({kafka_topic})")
    print(line)
    print(f"  RISK: {alert.risk_score:.2f} / flagged account {alert.flagged_account_id}")
    if alert.confidence is not None:
        print(f"  CONFIDENCE: {alert.confidence:.2f}")
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

    if not auto_act:
        return

    resolved_band = band or _band_from_score(alert.risk_score * 100)

    try:
        from shared.persistence import Store
        Store().save_alert(alert, resolved_band)
    except Exception as e:  # persistence must never crash the alert path
        log.warning(f"Persistence failed (continuing): {e}")

    try:
        from detection.auto_intervention import handle
        decision = handle(alert, resolved_band)
        print(f"  AUTO-RESPONSE: [{decision.tier}] {decision.justification}")
        try:
            from shared.persistence import Store
            Store().save_intervention(alert.complaint_id, decision)
        except Exception as e:
            log.warning(f"Persistence of intervention failed (continuing): {e}")
    except Exception as e:  # auto-intervention must never crash the alert path
        log.warning(f"Auto-intervention failed (continuing): {e}")
    print(line)


def _band_from_score(score_0_100: float) -> str:
    if score_0_100 >= 80:
        return "CRITICAL"
    if score_0_100 >= 60:
        return "HIGH"
    if score_0_100 >= 30:
        return "MEDIUM"
    return "LOW"