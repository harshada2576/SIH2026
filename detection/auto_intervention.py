"""detection/auto_intervention.py — turns a scored RiskAlert into action.

This is the answer to "should blocking be automatic?": a TIERED response,
not a single automatic freeze switch. Fully automatic freezing on every
CRITICAL score is a real risk (a false positive means locking a legitimate
customer out of their own money) — see Must-Read/PRD.md's Known Risks
section, which made this call for good reason. The tiers below keep the
mentor's "it should be automatic" requirement honest without inventing a
system that just freezes accounts on a hunch:

  CRITICAL + confidence HIGH   -> automatic FREEZE + LEA notify   (real risk, well-corroborated)
  CRITICAL + confidence < HIGH -> automatic HOLD + LEA notify     (real risk, less corroborated -> reversible action only)
  HIGH                         -> automatic soft NOTIFY to bank + LEA notify (no funds action)
  MEDIUM / LOW                 -> logged only, no external call

Every single decision — action taken or not — is written with an explicit
justification string to (a) stdout, (b) the audit ledger (audit/blockchain_lite.py)
so "justification for everything" is a real, replayable record, not a
one-off console print.

Calls to the mock services degrade gracefully (log + continue) if a service
isn't running, so a missing terminal window never takes down the detection
pipeline during a demo.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from audit.blockchain_lite import AuditLedger
from detection.confidence import confidence_label
from shared.schemas import RiskAlert

log = logging.getLogger("auto_intervention")

BANK_API_URL = os.environ.get("BANK_API_URL", "http://localhost:8001")
NCRP_API_URL = os.environ.get("NCRP_API_URL", "http://localhost:8002")
HTTP_TIMEOUT_SECONDS = 2.0


@dataclass
class InterventionDecision:
    tier: str          # "AUTO_FREEZE" | "AUTO_HOLD" | "SOFT_NOTIFY" | "LOG_ONLY"
    justification: str
    bank_action: Optional[str] = None      # "freeze" | "hold" | "notify" | None
    lea_notified: bool = False
    bank_call_ok: Optional[bool] = None
    lea_call_ok: Optional[bool] = None


def _post_json(url: str, payload: dict) -> tuple[bool, Optional[dict]]:
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        log.warning(f"Call to {url} failed (service not running?): {e}")
        return False, None


def decide(alert: RiskAlert, band: str) -> InterventionDecision:
    """Pure decision logic (no I/O) — kept separate from `handle()` so it's
    trivially unit-testable without spinning up the mock services."""
    confidence = alert.confidence if alert.confidence is not None else 0.0
    conf_label = confidence_label(confidence)

    if band == "CRITICAL" and conf_label == "HIGH":
        return InterventionDecision(
            tier="AUTO_FREEZE",
            bank_action="freeze",
            lea_notified=True,
            justification=(f"CRITICAL risk ({alert.risk_score:.2f}) with HIGH confidence "
                            f"({confidence:.2f}, {sum(1 for e in alert.evidence)} corroborating signals) "
                            f"-> automatic freeze + LEA notification. Reversible on human review."),
        )
    if band == "CRITICAL":
        return InterventionDecision(
            tier="AUTO_HOLD",
            bank_action="hold",
            lea_notified=True,
            justification=(f"CRITICAL risk ({alert.risk_score:.2f}) but confidence is only "
                            f"{conf_label} ({confidence:.2f}) -> automatic HOLD (reversible, funds not "
                            f"released but not fully frozen) + LEA notification, pending human review."),
        )
    if band == "HIGH":
        return InterventionDecision(
            tier="SOFT_NOTIFY",
            bank_action="notify",
            lea_notified=True,
            justification=(f"HIGH risk ({alert.risk_score:.2f}) -> soft alert to bank + LEA notify, "
                            f"no funds action. Awaiting investigator decision."),
        )
    return InterventionDecision(
        tier="LOG_ONLY",
        justification=f"{band} risk ({alert.risk_score:.2f}) -> below action threshold, logged only.",
    )


def handle(alert: RiskAlert, band: str, ledger: Optional[AuditLedger] = None) -> InterventionDecision:
    """Decide + actually call the mock bank/NCRP services + write to the audit ledger."""
    decision = decide(alert, band)
    ledger = ledger or AuditLedger()

    if decision.bank_action:
        ok, _ = _post_json(
            f"{BANK_API_URL}/accounts/{alert.flagged_account_id}/{decision.bank_action}",
            {"reason": decision.justification, "complaint_id": alert.complaint_id, "confidence": alert.confidence},
        )
        decision.bank_call_ok = ok

    if decision.lea_notified:
        ok, _ = _post_json(f"{NCRP_API_URL}/alerts", {
            "complaint_id": alert.complaint_id,
            "flagged_account_id": alert.flagged_account_id,
            "risk_score": alert.risk_score,
            "confidence": alert.confidence,
            "evidence": alert.evidence,
        })
        decision.lea_call_ok = ok

    ledger.append({
        "complaint_id": alert.complaint_id,
        "flagged_account_id": alert.flagged_account_id,
        "risk_score": alert.risk_score,
        "confidence": alert.confidence,
        "band": band,
        "tier": decision.tier,
        "bank_action": decision.bank_action,
        "lea_notified": decision.lea_notified,
        "justification": decision.justification,
    })

    log.info(f"[{decision.tier}] {alert.complaint_id}: {decision.justification}")
    return decision
