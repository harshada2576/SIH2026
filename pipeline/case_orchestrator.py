"""pipeline/case_orchestrator.py — Case Orchestration & Escalation Layer for SIH26184.

Connects the outputs of all existing project components:
- Detection Engine (scorer, rules, auto_intervention)
- Part 1: Confirmation & Transaction Control (TransactionControlManager, ConfirmationRecord)
- Part 2: Fund Traceability & Recovery (FundTraceabilityEngine, RecoveryCaseRecord)
- Part 3: Withdrawal & Geo Intelligence (WithdrawalGeoIntelligence, LocationEvidenceRecord)
- Part 4: CyberShield Bank Official Dashboard (CaseRecord, priority matrix)
- Part 5: Police Alert & Delivery Engine (PoliceAlertManager, PoliceAlertRecord)

Answers:
"When should a suspicious activity remain monitored, when should it become an active case,
 when should intervention escalate, and when should a bank official be given the option to alert police?"
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from audit.blockchain_lite import AuditLedger
from detection.transaction_control import TransactionControlManager
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from pipeline.notification_service import NotificationEvent, NotificationEventType, NotificationService
from pipeline.police_alert_delivery import PoliceAlertManager
from shared.persistence import Store
from shared.schemas import (
    CaseLifecycleState,
    CaseRecord,
    ConfirmationStatus,
    PoliceAlertStatus,
    TimelineEvent,
    _format_iso,
)

log = logging.getLogger("case_orchestrator")


class CaseOrchestrator:
    """Central orchestrator coordinating investigation lifecycles, state transitions, timeline tracking, and multi-component linkages."""

    def __init__(
        self,
        store: Optional[Store] = None,
        control_mgr: Optional[TransactionControlManager] = None,
        trace_engine: Optional[FundTraceabilityEngine] = None,
        geo_intel: Optional[WithdrawalGeoIntelligence] = None,
        police_mgr: Optional[PoliceAlertManager] = None,
        ledger: Optional[AuditLedger] = None,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self.store = store or Store()
        self.control_mgr = control_mgr or TransactionControlManager(store=self.store)
        self.trace_engine = trace_engine or FundTraceabilityEngine(store=self.store)
        self.geo_intel = geo_intel or WithdrawalGeoIntelligence(store=self.store)
        self.police_mgr = police_mgr or PoliceAlertManager(
            store=self.store, trace_engine=self.trace_engine, geo_intel=self.geo_intel
        )
        self.ledger = ledger or AuditLedger()
        self.notification_service = notification_service or NotificationService(store=self.store)

    # ------------------------------------------------------------------------
    # 1. Derived Priority & Police Eligibility Policy
    # ------------------------------------------------------------------------

    def evaluate_priority_and_eligibility(self, case_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Derive priority (LOW/MEDIUM/HIGH/CRITICAL) and police alert eligibility based on state & evidence."""
        state = case_dict.get("state", CaseLifecycleState.PRE_COMPLAINT_INTERVENTION)
        risk_score = float(case_dict.get("risk_score", 0.0))
        band = case_dict.get("band", "HIGH")
        withdrawals = case_dict.get("withdrawal_attempts", [])
        has_withdrawals = len(withdrawals) > 0
        is_fraud = state == CaseLifecycleState.CONFIRMED_FRAUD or case_dict.get("recovery_case_id") is not None
        has_fir = bool(case_dict.get("fir_number") or case_dict.get("complaint_id"))
        lea_status = case_dict.get("lea_notification_status", "NONE")

        # 1. State: Resolved / Legitimate
        if state in (CaseLifecycleState.RESOLVED, "CONFIRMED_LEGITIMATE", "DISMISSED"):
            return {"priority": "LOW", "police_alert_eligible": False}

        # 2. State: Confirmed Fraud, FIR, Police Sent/Investigating -> CRITICAL
        if is_fraud or has_fir or state in (CaseLifecycleState.POST_COMPLAINT_ESCALATED, CaseLifecycleState.POLICE_ALERT_SENT, CaseLifecycleState.UNDER_INVESTIGATION) or lea_status in ("SENT", "ACKNOWLEDGED", "UNDER_INVESTIGATION"):
            return {"priority": "CRITICAL", "police_alert_eligible": True}

        # 3. Cashout Attempt Detected or Withdrawal Evidence Present
        if state == CaseLifecycleState.CASHOUT_ATTEMPT_DETECTED or has_withdrawals:
            prio = "CRITICAL" if (risk_score >= 0.80 or band == "CRITICAL") else "HIGH"
            return {"priority": prio, "police_alert_eligible": True}

        # 4. Detection Engine Risk Bands
        if risk_score >= 0.80 or band == "CRITICAL":
            return {"priority": "CRITICAL", "police_alert_eligible": True}
        elif risk_score >= 0.60 or band == "HIGH":
            return {"priority": "HIGH", "police_alert_eligible": False}
        else:
            return {"priority": "MEDIUM", "police_alert_eligible": False}

    # ------------------------------------------------------------------------
    # 2. Suspicious Activity Ingestion & Accumulation (Deduplication)
    # ------------------------------------------------------------------------

    def ingest_suspicious_event(
        self,
        account_id: str,
        risk_score: float,
        confidence: float,
        evidence: List[str],
        predicted_terminals: Optional[List[Any]] = None,
        suspicious_amount: float = 0.0,
        transaction_id: Optional[str] = None,
        chain_id: Optional[str] = None,
        source: str = "DETECTION_ENGINE",
    ) -> CaseRecord:
        """Idempotently ingest a suspicious event, updating existing case or creating a new case."""
        now_str = datetime.now(timezone.utc).isoformat()

        # Deduplication search: locate existing active case by account_id, transaction_id, or chain_id
        active_cases = self.store.recent_cases(limit=50, account_id=account_id)
        existing_case_dict = None

        for c in active_cases:
            if c.get("state") not in (CaseLifecycleState.RESOLVED, "DISMISSED"):
                existing_case_dict = c
                break

        if not existing_case_dict and transaction_id:
            all_recent = self.store.recent_cases(limit=100)
            for c in all_recent:
                if c.get("root_transaction_id") == transaction_id or c.get("case_id") == f"CASE-{transaction_id}":
                    existing_case_dict = c
                    break

        if existing_case_dict:
            # Update existing case with accumulated evidence (Deduplication)
            cid = existing_case_dict["case_id"]
            merged_evidence = list(set(existing_case_dict.get("evidence", []) + list(evidence)))

            # Update highest risk score / confidence
            new_risk = max(float(existing_case_dict.get("risk_score", 0.0)), float(risk_score))
            new_conf = max(float(existing_case_dict.get("confidence", 0.0) or 0.0), float(confidence))
            band = "CRITICAL" if new_risk >= 0.80 else ("HIGH" if new_risk >= 0.60 else "MEDIUM")

            existing_case_dict["risk_score"] = new_risk
            existing_case_dict["confidence"] = new_conf
            existing_case_dict["band"] = band
            existing_case_dict["evidence"] = merged_evidence
            existing_case_dict["suspicious_amount"] = max(float(existing_case_dict.get("suspicious_amount", 0.0)), float(suspicious_amount))
            existing_case_dict["updated_at"] = now_str
            if transaction_id and not existing_case_dict.get("root_transaction_id"):
                existing_case_dict["root_transaction_id"] = transaction_id
            if chain_id and not existing_case_dict.get("chain_id"):
                existing_case_dict["chain_id"] = chain_id

            eval_res = self.evaluate_priority_and_eligibility(existing_case_dict)
            existing_case_dict["priority"] = eval_res["priority"]
            existing_case_dict["police_alert_eligible"] = eval_res["police_alert_eligible"]

            self.store.save_case(existing_case_dict)

            # Record timeline event
            event_id = f"TL-ACCUM-{uuid.uuid4().hex[:8]}"
            tl_event = TimelineEvent(
                event_id=event_id,
                case_id=cid,
                event_type="SUSPICIOUS_EVENT_ACCUMULATED",
                timestamp=now_str,
                source=source,
                details={
                    "risk_score": new_risk,
                    "confidence": new_conf,
                    "new_evidence_added": list(evidence),
                    "transaction_id": transaction_id,
                    "priority": eval_res["priority"],
                },
            )
            self.store.save_timeline_event(tl_event)

            log.info(f"[ORCHESTRATOR] Accumulated suspicious event into active case {cid} (Priority: {eval_res['priority']})")
            return self._dict_to_case_record(existing_case_dict)

        # Create New Case
        cid = f"CASE-{transaction_id}" if transaction_id else f"CASE-{uuid.uuid4().hex[:8]}"
        band = "CRITICAL" if risk_score >= 0.80 else ("HIGH" if risk_score >= 0.60 else "MEDIUM")

        temp_dict = {
            "case_id": cid,
            "flagged_account_id": account_id,
            "state": CaseLifecycleState.PRE_COMPLAINT_INTERVENTION,
            "risk_score": float(risk_score),
            "confidence": float(confidence),
            "band": band,
            "suspicious_amount": float(suspicious_amount),
            "protected_amount": float(suspicious_amount),
            "existing_balance": 20000.0,
            "evidence": list(evidence),
            "predicted_terminals": predicted_terminals or [],
            "root_transaction_id": transaction_id,
            "chain_id": chain_id,
            "created_at": now_str,
            "updated_at": now_str,
        }
        eval_res = self.evaluate_priority_and_eligibility(temp_dict)

        case_rec = CaseRecord(
            case_id=cid,
            flagged_account_id=account_id,
            state=CaseLifecycleState.PRE_COMPLAINT_INTERVENTION,
            risk_score=float(risk_score),
            confidence=float(confidence),
            band=band,
            priority=eval_res["priority"],
            suspicious_amount=float(suspicious_amount),
            protected_amount=float(suspicious_amount),
            existing_balance=20000.0,
            evidence=list(evidence),
            predicted_terminals=predicted_terminals or [],
            root_transaction_id=transaction_id,
            chain_id=chain_id,
            police_alert_eligible=eval_res["police_alert_eligible"],
            created_at=now_str,
            updated_at=now_str,
        )

        self.store.save_case(case_rec)

        # Record timeline event
        event_id = f"TL-INIT-{uuid.uuid4().hex[:8]}"
        tl_event = TimelineEvent(
            event_id=event_id,
            case_id=cid,
            event_type="CASE_INITIALIZED",
            timestamp=now_str,
            source=source,
            details={
                "account_id": account_id,
                "risk_score": risk_score,
                "confidence": confidence,
                "priority": eval_res["priority"],
                "evidence": list(evidence),
            },
        )
        self.store.save_timeline_event(tl_event)

        self.ledger.append({
            "event": "CASE_ORCHESTRATION_INITIALIZED",
            "case_id": cid,
            "account_id": account_id,
            "risk_score": risk_score,
            "priority": eval_res["priority"],
            "timestamp": now_str,
        })

        # Operational Notification: HIGH_RISK_CASE
        if eval_res["priority"] in ("HIGH", "CRITICAL") or risk_score >= 0.60:
            term_id = None
            if predicted_terminals and len(predicted_terminals) > 0:
                first_term = predicted_terminals[0]
                term_id = first_term.get("terminal_id") if isinstance(first_term, dict) else getattr(first_term, "terminal_id", str(first_term))
            try:
                self.notification_service.notify(NotificationEvent(
                    event_type=NotificationEventType.HIGH_RISK_CASE,
                    case_id=cid,
                    account_id=account_id,
                    amount=float(suspicious_amount),
                    terminal_id=term_id,
                    timestamp=now_str,
                    confidence=float(confidence),
                    risk_score=float(risk_score),
                    evidence=list(evidence),
                    status=CaseLifecycleState.PRE_COMPLAINT_INTERVENTION,
                    details={"priority": eval_res["priority"], "transaction_id": transaction_id},
                ))
            except Exception as notif_err:
                log.warning(f"[ORCHESTRATOR] Notification dispatch failed (continuing): {notif_err}")

        log.info(f"[ORCHESTRATOR] Initialized case {cid} for account {account_id} (Priority: {eval_res['priority']})")
        return case_rec

    # ------------------------------------------------------------------------
    # 3. Confirmation Integration (Part 1 -> Part 6 Orchestration)
    # ------------------------------------------------------------------------

    def handle_confirmation_update(
        self,
        confirmation_id: str,
        status: str,
        outcome: Optional[str] = None,
        notes: str = "",
    ) -> Optional[CaseRecord]:
        """Orchestrate case escalation or resolution based on customer confirmation result."""
        conf = self.store.get_confirmation(confirmation_id)
        if not conf:
            log.warning(f"[ORCHESTRATOR] Confirmation {confirmation_id} not found in store.")
            return None

        tx_id = conf["transaction_id"]
        cid = conf.get("case_id")

        # Find case by confirmation case_id or root_transaction_id
        case_dict = self.store.get_case(cid) if cid else None
        if not case_dict:
            recent = self.store.recent_cases(limit=100)
            for c in recent:
                if c.get("root_transaction_id") == tx_id or c.get("confirmation_id") == confirmation_id:
                    case_dict = c
                    break

        if not case_dict:
            log.warning(f"[ORCHESTRATOR] No correlated case found for confirmation {confirmation_id}")
            return None

        cid = case_dict["case_id"]
        now_str = datetime.now(timezone.utc).isoformat()
        case_dict["confirmation_id"] = confirmation_id

        if status == ConfirmationStatus.CONFIRMED_LEGITIMATE:
            # Transition to RESOLVED / CONFIRMED_LEGITIMATE
            case_dict["state"] = CaseLifecycleState.RESOLVED
            case_dict["priority"] = "LOW"
            case_dict["police_alert_eligible"] = False
            case_dict["bank_hold_status"] = "NONE"
            case_dict["resolution_reason"] = f"CONFIRMED_LEGITIMATE: {notes or 'Customer verified transfer'}"
            case_dict["resolved_at"] = now_str
            case_dict["updated_at"] = now_str

            self.store.save_case(case_dict)

            # Record timeline
            tl_event = TimelineEvent(
                event_id=f"TL-CONF-LEGIT-{uuid.uuid4().hex[:8]}",
                case_id=cid,
                event_type="CONFIRMATION_LEGITIMATE_RESOLVED",
                timestamp=now_str,
                source="CUSTOMER_CONFIRMATION",
                details={
                    "confirmation_id": confirmation_id,
                    "transaction_id": tx_id,
                    "notes": notes,
                },
            )
            self.store.save_timeline_event(tl_event)

            log.info(f"[ORCHESTRATOR] Case {cid} RESOLVED via CONFIRMED_LEGITIMATE.")

        elif status == ConfirmationStatus.CONFIRMED_FRAUD:
            # Transition to CONFIRMED_FRAUD & Trigger Part 2 Recovery Case
            case_dict["state"] = CaseLifecycleState.CONFIRMED_FRAUD
            case_dict["priority"] = "CRITICAL"
            case_dict["police_alert_eligible"] = True
            case_dict["bank_hold_status"] = "FULL_FREEZE"
            case_dict["updated_at"] = now_str

            # Trigger Part 2 recovery workflow
            rec_case = self.trace_engine.handle_fraud_confirmation(
                root_transaction_id=tx_id, case_id=cid, notes=notes
            )
            case_dict["recovery_case_id"] = rec_case.case_id

            self.store.save_case(case_dict)

            # Record timeline
            tl_event = TimelineEvent(
                event_id=f"TL-CONF-FRAUD-{uuid.uuid4().hex[:8]}",
                case_id=cid,
                event_type="CONFIRMATION_FRAUD_ESCALATED",
                timestamp=now_str,
                source="CUSTOMER_CONFIRMATION",
                details={
                    "confirmation_id": confirmation_id,
                    "transaction_id": tx_id,
                    "recovery_case_id": rec_case.case_id,
                    "notes": notes,
                },
            )
            self.store.save_timeline_event(tl_event)

            # Operational Notification: CONFIRMED_FRAUD
            try:
                self.notification_service.notify(NotificationEvent(
                    event_type=NotificationEventType.CONFIRMED_FRAUD,
                    case_id=cid,
                    account_id=case_dict.get("flagged_account_id", ""),
                    amount=float(case_dict.get("suspicious_amount", 0.0)),
                    timestamp=now_str,
                    confidence=float(case_dict.get("confidence", 0.95)),
                    risk_score=float(case_dict.get("risk_score", 0.95)),
                    evidence=list(case_dict.get("evidence", [])),
                    status=CaseLifecycleState.CONFIRMED_FRAUD,
                    details={"recovery_case_id": rec_case.case_id, "notes": notes},
                ))
            except Exception as notif_err:
                log.warning(f"[ORCHESTRATOR] Notification dispatch failed (continuing): {notif_err}")

            log.info(f"[ORCHESTRATOR] Case {cid} ESCALATED to CONFIRMED_FRAUD (Recovery Case: {rec_case.case_id}).")

        return self._dict_to_case_record(case_dict)

    # ------------------------------------------------------------------------
    # 4. Withdrawal & ATM Event Integration (Part 3 -> Part 6 Orchestration)
    # ------------------------------------------------------------------------

    def handle_withdrawal_attempt(
        self,
        attempt_id: str,
        account_id: str,
        terminal_id: str,
        amount_inr: float,
        timestamp: Optional[Union[str, datetime]] = None,
        case_id: Optional[str] = None,
    ) -> CaseRecord:
        """Process cashout withdrawal attempt, update case state, evaluate ATM recurrence, and update timeline."""
        # 1. Process attempt via Part 3 Geo Intel
        attempt_event = self.geo_intel.process_withdrawal_attempt(
            attempt_id=attempt_id,
            account_id=account_id,
            terminal_id=terminal_id,
            amount_inr=amount_inr,
            timestamp=timestamp,
            case_id=case_id,
        )

        matched_cid = attempt_event.correlated_case_id or case_id
        now_str = datetime.now(timezone.utc).isoformat()

        # Locate case
        case_dict = self.store.get_case(matched_cid) if matched_cid else None
        if not case_dict:
            # Create case if none existed
            c_rec = self.ingest_suspicious_event(
                account_id=account_id,
                risk_score=0.85,
                confidence=0.90,
                evidence=[f"Cashout withdrawal attempt detected at physical ATM {terminal_id}"],
                predicted_terminals=[{"terminal_id": terminal_id, "probability": 0.95}],
                suspicious_amount=amount_inr,
                source="ATM_WITHDRAWAL_INTELLIGENCE",
            )
            case_dict = c_rec.to_dict()
            matched_cid = case_dict["case_id"]

        # Update case lifecycle state
        if case_dict.get("state") in (CaseLifecycleState.OBSERVED, CaseLifecycleState.SUSPICIOUS, CaseLifecycleState.PREDICTED, CaseLifecycleState.PRE_COMPLAINT_INTERVENTION):
            case_dict["state"] = CaseLifecycleState.CASHOUT_ATTEMPT_DETECTED

        # Check repeated ATM targeting (Part 3)
        term_hist = self.geo_intel.get_account_terminal_history(account_id, terminal_id)
        if term_hist.get("escalation_state") == "PERSISTENT_TERMINAL_RISK":
            merged_ev = list(set(case_dict.get("evidence", []) + [f"Repeated ATM targeting: PERSISTENT_TERMINAL_RISK at {terminal_id} ({term_hist.get('attempt_count')} attempts)"]))
            case_dict["evidence"] = merged_ev

        eval_res = self.evaluate_priority_and_eligibility(case_dict)
        case_dict["priority"] = eval_res["priority"]
        case_dict["police_alert_eligible"] = eval_res["police_alert_eligible"]
        case_dict["updated_at"] = now_str

        self.store.save_case(case_dict)

        # Record timeline event
        tl_event = TimelineEvent(
            event_id=f"TL-WITHDRAW-{uuid.uuid4().hex[:8]}",
            case_id=matched_cid,
            event_type="CASHOUT_ATTEMPT_RECORDED",
            timestamp=now_str,
            source="ATM_WITHDRAWAL_INTELLIGENCE",
            details={
                "attempt_id": attempt_id,
                "terminal_id": terminal_id,
                "amount": amount_inr,
                "status": attempt_event.status,
                "is_blocked": attempt_event.is_blocked,
                "reason": attempt_event.reason,
            },
        )
        self.store.save_timeline_event(tl_event)

        # Operational Notification: CASHOUT_ATTEMPT_DETECTED & WITHDRAWAL_BLOCKED
        try:
            self.notification_service.notify(NotificationEvent(
                event_type=NotificationEventType.CASHOUT_ATTEMPT_DETECTED,
                case_id=matched_cid,
                account_id=account_id,
                amount=amount_inr,
                terminal_id=terminal_id,
                terminal_location=getattr(attempt_event, "location", None) or terminal_id,
                timestamp=now_str,
                status=str(attempt_event.status),
                details={"attempt_id": attempt_id, "is_blocked": bool(attempt_event.is_blocked)},
            ))

            if attempt_event.is_blocked or str(attempt_event.status).upper() in ("BLOCKED", "INTERCEPTED"):
                self.notification_service.notify(NotificationEvent(
                    event_type=NotificationEventType.WITHDRAWAL_BLOCKED,
                    case_id=matched_cid,
                    account_id=account_id,
                    amount=amount_inr,
                    terminal_id=terminal_id,
                    terminal_location=getattr(attempt_event, "location", None) or terminal_id,
                    timestamp=now_str,
                    status=str(attempt_event.status),
                    details={"attempt_id": attempt_id, "reason": attempt_event.reason},
                ))
        except Exception as notif_err:
            log.warning(f"[ORCHESTRATOR] Withdrawal notification dispatch failed (continuing): {notif_err}")

        log.info(f"[ORCHESTRATOR] Withdrawal attempt recorded for case {matched_cid} at {terminal_id} (Status: {attempt_event.status})")
        return self._dict_to_case_record(case_dict)

    # ------------------------------------------------------------------------
    # 5. Formal Complaint / FIR Escalation
    # ------------------------------------------------------------------------

    def attach_complaint_fir(
        self,
        case_id: str,
        complaint_id: str,
        fir_number: Optional[str] = None,
        victim_account: Optional[str] = None,
        reported_loss: Optional[float] = None,
        source: str = "NCRP_1930_PORTAL",
    ) -> CaseRecord:
        """Attach formal NCRP complaint / FIR number and escalate case to POST_COMPLAINT_ESCALATED."""
        case_dict = self.store.get_case(case_id)
        if not case_dict:
            raise KeyError(f"Case not found: {case_id}")

        now_str = datetime.now(timezone.utc).isoformat()
        case_dict["complaint_id"] = complaint_id
        if fir_number:
            case_dict["fir_number"] = fir_number
        case_dict["state"] = CaseLifecycleState.POST_COMPLAINT_ESCALATED
        case_dict["priority"] = "CRITICAL"
        case_dict["police_alert_eligible"] = True
        case_dict["bank_hold_status"] = "FULL_FREEZE"
        case_dict["updated_at"] = now_str

        merged_ev = list(set(case_dict.get("evidence", []) + [f"Formal Complaint/FIR Attached: {complaint_id} ({fir_number or 'NCRP Escalated'})"]))
        case_dict["evidence"] = merged_ev

        self.store.save_case(case_dict)

        # Record timeline event
        tl_event = TimelineEvent(
            event_id=f"TL-FIR-{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            event_type="FORMAL_COMPLAINT_FIR_ATTACHED",
            timestamp=now_str,
            source=source,
            details={
                "complaint_id": complaint_id,
                "fir_number": fir_number,
                "victim_account": victim_account,
                "reported_loss": reported_loss,
            },
        )
        self.store.save_timeline_event(tl_event)

        # Operational Notification: CASE_ESCALATED
        try:
            self.notification_service.notify(NotificationEvent(
                event_type=NotificationEventType.CASE_ESCALATED,
                case_id=case_id,
                account_id=case_dict.get("flagged_account_id", ""),
                amount=float(case_dict.get("suspicious_amount", 0.0)),
                timestamp=now_str,
                status=CaseLifecycleState.POST_COMPLAINT_ESCALATED,
                evidence=list(case_dict.get("evidence", [])),
                details={"complaint_id": complaint_id, "fir_number": fir_number},
            ))
        except Exception as notif_err:
            log.warning(f"[ORCHESTRATOR] Escalation notification dispatch failed (continuing): {notif_err}")

        log.info(f"[ORCHESTRATOR] Attached FIR/Complaint {complaint_id} to case {case_id}. State: POST_COMPLAINT_ESCALATED.")
        return self._dict_to_case_record(case_dict)

    # ------------------------------------------------------------------------
    # 6. Manual Bank Escalation, Resolution & Dismissal
    # ------------------------------------------------------------------------

    def escalate_case(
        self,
        case_id: str,
        reason: str = "",
        actor_role: str = "BANK_OFFICIAL",
    ) -> CaseRecord:
        """Explicit bank official escalation of a case."""
        case_dict = self.store.get_case(case_id)
        if not case_dict:
            raise KeyError(f"Case not found: {case_id}")

        now_str = datetime.now(timezone.utc).isoformat()
        case_dict["escalation_level"] = int(case_dict.get("escalation_level", 1)) + 1
        case_dict["priority"] = "CRITICAL"
        case_dict["police_alert_eligible"] = True
        case_dict["updated_at"] = now_str

        if reason:
            merged_ev = list(set(case_dict.get("evidence", []) + [f"Manual Bank Escalation: {reason}"]))
            case_dict["evidence"] = merged_ev

        self.store.save_case(case_dict)

        tl_event = TimelineEvent(
            event_id=f"TL-ESCALATE-{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            event_type="MANUAL_CASE_ESCALATED",
            timestamp=now_str,
            source=actor_role,
            details={"reason": reason, "escalation_level": case_dict["escalation_level"]},
        )
        self.store.save_timeline_event(tl_event)

        # Operational Notification: CASE_ESCALATED
        try:
            self.notification_service.notify(NotificationEvent(
                event_type=NotificationEventType.CASE_ESCALATED,
                case_id=case_id,
                account_id=case_dict.get("flagged_account_id", ""),
                amount=float(case_dict.get("suspicious_amount", 0.0)),
                timestamp=now_str,
                status=case_dict.get("state", CaseLifecycleState.POST_COMPLAINT_ESCALATED),
                evidence=list(case_dict.get("evidence", [])),
                details={"reason": reason, "escalation_level": case_dict["escalation_level"]},
            ))
        except Exception as notif_err:
            log.warning(f"[ORCHESTRATOR] Escalation notification dispatch failed (continuing): {notif_err}")

        log.info(f"[ORCHESTRATOR] Case {case_id} manually escalated to CRITICAL by {actor_role}.")
        return self._dict_to_case_record(case_dict)

    def resolve_case(
        self,
        case_id: str,
        reason: str = "Resolved",
        actor_id: Optional[str] = None,
    ) -> CaseRecord:
        """Mark case as RESOLVED."""
        case_dict = self.store.get_case(case_id)
        if not case_dict:
            raise KeyError(f"Case not found: {case_id}")

        now_str = datetime.now(timezone.utc).isoformat()
        case_dict["state"] = CaseLifecycleState.RESOLVED
        case_dict["priority"] = "LOW"
        case_dict["police_alert_eligible"] = False
        case_dict["resolution_reason"] = reason
        case_dict["resolved_at"] = now_str
        case_dict["updated_at"] = now_str

        self.store.save_case(case_dict)

        tl_event = TimelineEvent(
            event_id=f"TL-RESOLVE-{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            event_type="CASE_RESOLVED",
            timestamp=now_str,
            source=actor_id or "BANK_OFFICIAL",
            details={"reason": reason, "resolved_at": now_str},
        )
        self.store.save_timeline_event(tl_event)

        log.info(f"[ORCHESTRATOR] Case {case_id} RESOLVED. Reason: {reason}")
        return self._dict_to_case_record(case_dict)

    def dismiss_case(
        self,
        case_id: str,
        reason: str = "False Positive",
        actor_id: Optional[str] = None,
    ) -> CaseRecord:
        """Dismiss case as False Positive and clear provisional restrictions."""
        case_dict = self.store.get_case(case_id)
        if not case_dict:
            raise KeyError(f"Case not found: {case_id}")

        now_str = datetime.now(timezone.utc).isoformat()
        case_dict["state"] = CaseLifecycleState.RESOLVED
        case_dict["priority"] = "LOW"
        case_dict["police_alert_eligible"] = False
        case_dict["bank_hold_status"] = "NONE"
        case_dict["resolution_reason"] = f"DISMISSED: {reason}"
        case_dict["resolved_at"] = now_str
        case_dict["updated_at"] = now_str

        self.store.save_case(case_dict)

        tl_event = TimelineEvent(
            event_id=f"TL-DISMISS-{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            event_type="CASE_DISMISSED",
            timestamp=now_str,
            source=actor_id or "BANK_OFFICIAL",
            details={"reason": reason},
        )
        self.store.save_timeline_event(tl_event)

        log.info(f"[ORCHESTRATOR] Case {case_id} DISMISSED as false positive. Reason: {reason}")
        return self._dict_to_case_record(case_dict)

    # ------------------------------------------------------------------------
    # 7. Police Alert Action Integration (Part 5 -> Part 6 Orchestration)
    # ------------------------------------------------------------------------

    def trigger_police_alert(
        self,
        case_id: str,
        actor_role: str = "BANK_OFFICIAL",
        source: str = "CyberShield Bank Official Dashboard",
    ) -> Dict[str, Any]:
        """Bank official explicit click 'ALERT POLICE' -> delegates to Part 5 PoliceAlertManager and links status."""
        case_dict = self.store.get_case(case_id)
        if not case_dict:
            raise KeyError(f"Case not found: {case_id}")

        # Delegate to Part 5 PoliceAlertManager
        police_alert_rec = self.police_mgr.create_police_alert(
            case_id=case_id, caller_role=actor_role, source=source
        )

        now_str = datetime.now(timezone.utc).isoformat()
        case_dict["state"] = CaseLifecycleState.POLICE_ALERT_SENT
        case_dict["police_alert_id"] = police_alert_rec.police_alert_id
        case_dict["lea_notification_status"] = PoliceAlertStatus.SENT
        case_dict["priority"] = "CRITICAL"
        case_dict["updated_at"] = now_str

        self.store.save_case(case_dict)

        tl_event = TimelineEvent(
            event_id=f"TL-POLICE-{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            event_type="POLICE_ALERT_DISPATCHED",
            timestamp=now_str,
            source=source,
            details={
                "police_alert_id": police_alert_rec.police_alert_id,
                "priority": police_alert_rec.priority,
            },
        )
        self.store.save_timeline_event(tl_event)

        # Operational Notification: POLICE_ALERT_SENT
        try:
            tid = None
            if police_alert_rec.nearby_terminals:
                first_term = police_alert_rec.nearby_terminals[0]
                tid = first_term.get("terminal_id") if isinstance(first_term, dict) else getattr(first_term, "terminal_id", str(first_term))
            self.notification_service.notify(NotificationEvent(
                event_type=NotificationEventType.POLICE_ALERT_SENT,
                case_id=case_id,
                account_id=case_dict.get("flagged_account_id", ""),
                amount=float(case_dict.get("suspicious_amount", 0.0)),
                terminal_id=tid,
                timestamp=now_str,
                status=CaseLifecycleState.POLICE_ALERT_SENT,
                details={"police_alert_id": police_alert_rec.police_alert_id, "priority": police_alert_rec.priority},
            ))
        except Exception as notif_err:
            log.warning(f"[ORCHESTRATOR] Police alert notification dispatch failed (continuing): {notif_err}")

        log.info(f"[ORCHESTRATOR] Police alert {police_alert_rec.police_alert_id} linked to case {case_id}.")
        return {
            "status": "SUCCESS",
            "case": self._dict_to_case_record(case_dict).to_dict(),
            "police_alert": police_alert_rec.to_dict(),
        }

    # ------------------------------------------------------------------------
    # 8. Unified Case Query Interfaces
    # ------------------------------------------------------------------------

    def get_case_details(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Assemble full unified investigation case object including linkages & timeline events."""
        case_dict = self.store.get_case(case_id)
        if not case_dict:
            return None

        # Re-evaluate priority & eligibility
        eval_res = self.evaluate_priority_and_eligibility(case_dict)
        case_dict["priority"] = eval_res["priority"]
        case_dict["police_alert_eligible"] = eval_res["police_alert_eligible"]

        # Fetch timeline events
        case_dict["timeline_events"] = self.store.get_case_timeline(case_id)

        # Link recovery case object if present
        rec_id = case_dict.get("recovery_case_id")
        if rec_id:
            case_dict["recovery_case"] = self.store.get_recovery_case(rec_id)

        # Link police alert object if present
        pol_id = case_dict.get("police_alert_id")
        if pol_id:
            case_dict["police_alert"] = self.store.get_police_alert(pol_id)

        return case_dict

    def get_case_timeline(self, case_id: str) -> List[Dict[str, Any]]:
        """Retrieve chronological timeline events for a case."""
        return self.store.get_case_timeline(case_id)

    def list_cases(
        self,
        limit: int = 50,
        state: Optional[str] = None,
        priority: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List filterable cases."""
        cases = self.store.recent_cases(limit=limit, state=state, priority=priority, account_id=account_id)
        for c in cases:
            eval_res = self.evaluate_priority_and_eligibility(c)
            c["priority"] = eval_res["priority"]
            c["police_alert_eligible"] = eval_res["police_alert_eligible"]
        return cases

    def _dict_to_case_record(self, data: Dict[str, Any]) -> CaseRecord:
        """Convert a dictionary to a strongly-typed CaseRecord object."""
        return CaseRecord(
            case_id=data["case_id"],
            flagged_account_id=data["flagged_account_id"],
            state=data.get("state", CaseLifecycleState.PRE_COMPLAINT_INTERVENTION),
            risk_score=float(data.get("risk_score", 0.0)),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            band=data.get("band", "HIGH"),
            priority=data.get("priority", "HIGH"),
            suspicious_amount=float(data.get("suspicious_amount", 0.0)),
            protected_amount=float(data.get("protected_amount", 0.0)),
            existing_balance=float(data.get("existing_balance", 20000.0)),
            money_trail=data.get("money_trail", []),
            predicted_terminals=data.get("predicted_terminals", []),
            predicted_window_start=data.get("predicted_window_start", ""),
            predicted_window_end=data.get("predicted_window_end", ""),
            evidence=data.get("evidence", []),
            bank_hold_status=data.get("bank_hold_status", "NONE"),
            terminal_block_status=data.get("terminal_block_status", "NONE"),
            lea_notification_status=data.get("lea_notification_status", "NONE"),
            withdrawal_attempts=data.get("withdrawal_attempts", []),
            complaint_id=data.get("complaint_id"),
            fir_number=data.get("fir_number"),
            escalation_level=int(data.get("escalation_level", 1)),
            police_alert_eligible=bool(data.get("police_alert_eligible", False)),
            police_alert_id=data.get("police_alert_id"),
            recovery_case_id=data.get("recovery_case_id"),
            root_transaction_id=data.get("root_transaction_id"),
            chain_id=data.get("chain_id"),
            confirmation_id=data.get("confirmation_id"),
            resolution_reason=data.get("resolution_reason"),
            resolved_at=data.get("resolved_at"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
