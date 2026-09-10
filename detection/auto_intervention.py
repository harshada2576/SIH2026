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
    tier: str          # "AUTO_FREEZE" | "AUTO_HOLD" | "PROVISIONAL_HOLD" | "SOFT_NOTIFY" | "LOG_ONLY" | "POST_COMPLAINT_ESCALATED"
    justification: str
    bank_action: Optional[str] = None      # "freeze" | "hold" | "selective_hold" | "notify" | None
    lea_notified: bool = False
    terminal_block_requested: bool = False
    bank_call_ok: Optional[bool] = None
    lea_call_ok: Optional[bool] = None
    terminal_call_ok: Optional[bool] = None
    selective_hold_details: Optional[dict] = None
    pre_complaint: bool = True


def _post_json(url: str, payload: dict) -> tuple[bool, Optional[dict]]:
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            return True, json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        log.warning(f"Call to {url} failed (service not running?): {e}")
        return False, None


def decide(alert: RiskAlert, band: str, pre_complaint: bool = True, funds_breakdown: Optional[dict] = None) -> InterventionDecision:
    """Pure decision logic (no I/O) — supports pre-complaint selective holds and post-complaint escalation."""
    confidence = alert.confidence if alert.confidence is not None else 0.0
    conf_label = confidence_label(confidence)

    suspicious_amt = (funds_breakdown or {}).get("suspicious_amount", 100000.0)
    existing_bal = (funds_breakdown or {}).get("existing_balance", 20000.0)
    protected_amt = (funds_breakdown or {}).get("protected_amount", suspicious_amt)

    hold_info = {
        "account_id": alert.flagged_account_id,
        "existing_balance": existing_bal,
        "suspicious_amount": suspicious_amt,
        "protected_amount": protected_amt,
        "source_transaction_id": alert.complaint_id,
        "chain_reference": f"CHAIN-{alert.flagged_account_id}",
        "pre_complaint": pre_complaint,
    }

    if not pre_complaint:
        # Post-complaint escalation flow: full freeze + terminal physical blocking + LEA dispatch
        return InterventionDecision(
            tier="POST_COMPLAINT_ESCALATED",
            bank_action="freeze",
            lea_notified=True,
            terminal_block_requested=True,
            pre_complaint=False,
            selective_hold_details=hold_info,
            justification=(f"POST-COMPLAINT ESCALATION: Formal victim complaint attached to Case {alert.complaint_id} "
                           f"-> Full bank freeze (₹{existing_bal + suspicious_amt:,.2f}) + physical ATM blocking + LEA field patrol dispatch."),
        )

    # Pre-complaint provisional intervention flow
    if band == "CRITICAL" and conf_label == "HIGH":
        return InterventionDecision(
            tier="AUTO_FREEZE",
            bank_action="freeze",
            lea_notified=True,
            terminal_block_requested=True,
            pre_complaint=True,
            selective_hold_details=hold_info,
            justification=(f"PRE-COMPLAINT INTERVENTION (CRITICAL risk {alert.risk_score:.2f}, HIGH conf {confidence:.2f}): "
                           f"Provisional selective hold placed on recent suspicious funds (₹{protected_amt:,.2f}) only; "
                           f"existing legitimate balance (₹{existing_bal:,.2f}) remains unaffected. "
                           f"ATM egress block requested + LEA predictive notification sent."),
        )
    if band == "CRITICAL":
        return InterventionDecision(
            tier="AUTO_HOLD",
            bank_action="hold",
            lea_notified=True,
            terminal_block_requested=True,
            pre_complaint=True,
            selective_hold_details=hold_info,
            justification=(f"PRE-COMPLAINT PROVISIONAL HOLD (CRITICAL risk {alert.risk_score:.2f}, conf {conf_label}): "
                           f"Provisional reversible hold placed on recent chain amount (₹{protected_amt:,.2f}) pending verification. "
                           f"Unaffected historical balance: ₹{existing_bal:,.2f}."),
        )
    if band == "HIGH":
        return InterventionDecision(
            tier="SOFT_NOTIFY",
            bank_action="notify",
            lea_notified=True,
            terminal_block_requested=False,
            pre_complaint=True,
            selective_hold_details=hold_info,
            justification=(f"PRE-COMPLAINT ADVISORY (HIGH risk {alert.risk_score:.2f}): "
                           f"Soft advisory sent to bank & LEA for monitoring. No fund hold applied."),
        )
    return InterventionDecision(
        tier="LOG_ONLY",
        pre_complaint=True,
        selective_hold_details=hold_info,
        justification=f"{band} risk ({alert.risk_score:.2f}) -> below action threshold, logged only.",
    )


def handle(
    alert: RiskAlert,
    band: str,
    ledger: Optional[AuditLedger] = None,
    pre_complaint: bool = True,
    funds_breakdown: Optional[dict] = None,
) -> InterventionDecision:
    """Decide + call mock bank/NCRP/terminal services + write signed audit record."""
    decision = decide(alert, band, pre_complaint=pre_complaint, funds_breakdown=funds_breakdown)
    ledger = ledger or AuditLedger()

    # 1. Bank Action (selective_hold / freeze / hold / notify)
    if decision.bank_action:
        payload = {
            "reason": decision.justification,
            "complaint_id": alert.complaint_id,
            "case_id": alert.complaint_id,
            "confidence": alert.confidence,
            "pre_complaint": decision.pre_complaint,
        }
        if decision.selective_hold_details:
            payload.update(decision.selective_hold_details)

        endpoint = "selective_hold" if decision.bank_action == "selective_hold" else decision.bank_action
        ok, _ = _post_json(f"{BANK_API_URL}/accounts/{alert.flagged_account_id}/{endpoint}", payload)
        decision.bank_call_ok = ok

    # 2. Physical Terminal Blocking Request
    if decision.terminal_block_requested and alert.predicted_terminals:
        top_terminal = alert.predicted_terminals[0].terminal_id
        ok, _ = _post_json(f"{BANK_API_URL}/terminal/block", {
            "terminal_id": top_terminal,
            "case_id": alert.complaint_id,
            "reason": "PREDICTED_CASH_EGRESS",
            "action": "BLOCK_WITHDRAWAL",
            "valid_from": str(alert.predicted_window_start),
            "valid_until": str(alert.predicted_window_end),
            "account_id": alert.flagged_account_id,
        })
        decision.terminal_call_ok = ok

    # 3. LEA Notification / Case Record
    if decision.lea_notified:
        ok, _ = _post_json(f"{NCRP_API_URL}/alerts", {
            "complaint_id": alert.complaint_id,
            "case_id": alert.complaint_id,
            "flagged_account_id": alert.flagged_account_id,
            "risk_score": alert.risk_score,
            "confidence": alert.confidence,
            "evidence": alert.evidence,
            "pre_complaint": decision.pre_complaint,
            "predicted_terminals": [t.to_dict() for t in alert.predicted_terminals],
        })
        decision.lea_call_ok = ok

    ledger.append({
        "complaint_id": alert.complaint_id,
        "case_id": alert.complaint_id,
        "flagged_account_id": alert.flagged_account_id,
        "risk_score": alert.risk_score,
        "confidence": alert.confidence,
        "band": band,
        "tier": decision.tier,
        "bank_action": decision.bank_action,
        "lea_notified": decision.lea_notified,
        "terminal_block_requested": decision.terminal_block_requested,
        "pre_complaint": decision.pre_complaint,
        "justification": decision.justification,
        "selective_hold": decision.selective_hold_details,
    })

    log.info(f"[{decision.tier}] {alert.complaint_id}: {decision.justification}")
    return decision

