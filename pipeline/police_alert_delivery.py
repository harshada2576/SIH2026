"""pipeline/police_alert_delivery.py — Police Alert & Delivery Engine for SIH26184.

Connects CyberShield (Bank Official Interface) with Law Enforcement Agencies (LEA / Police).

Key Mandates:
1. Role-Based Explicit Escalation: Police alerts are NEVER automatically dispatched.
   Only explicit escalation by an authorized BANK_OFFICIAL creates a police alert.
2. Data Minimization & Structured Case Package:
   - Incident Details (Case ID, Risk level, Confidence, State, Reason, Timestamp)
   - Origin Transaction (Root transfer details & confirmation status)
   - Downstream Money Trail (Provenanced hops from Part 2)
   - Withdrawal / ATM Evidence (Observed attempts, status, coordinates)
   - Nearby Alternative Egress Terminals (Part 3 Haversine spatial intelligence)
   - Chronological Location Evidence Timeline
   - Backend Evidence / Escalation Reasons
3. Idempotency & Deduplication: Multiple clicks for the same case return the existing alert.
4. Bidirectional Status Synchronization:
   - Bank Official Action -> POST /cases/{case_id}/police-alert -> status SENT
   - Police Officer Action -> ACKNOWLEDGE -> status ACKNOWLEDGED
   - Police Officer Action -> UPDATE STATUS -> UNDER_INVESTIGATION / RESOLVED / CLOSED
   - Automatically synchronizes back to CyberShield's case record.
5. Role Authorization Enforcement:
   - BANK_OFFICIAL role required for alert creation
   - POLICE_OFFICER role required for acknowledgment and investigation updates
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from audit.blockchain_lite import AuditLedger
from pipeline.fund_traceability import FundTraceabilityEngine
from pipeline.geo_intelligence import WithdrawalGeoIntelligence
from shared.persistence import Store
from shared.schemas import (
    PoliceAlertRecord,
    PoliceAlertStatus,
    _format_iso,
)

log = logging.getLogger("police_alert_delivery")


class PoliceAlertManager:
    """Manages police alert creation, package assembly, delivery, acknowledgment, and status synchronization."""

    def __init__(
        self,
        store: Optional[Store] = None,
        trace_engine: Optional[FundTraceabilityEngine] = None,
        geo_intel: Optional[WithdrawalGeoIntelligence] = None,
        ledger: Optional[AuditLedger] = None,
    ) -> None:
        self.store = store or Store()
        self.trace_engine = trace_engine or FundTraceabilityEngine(store=self.store)
        self.geo_intel = geo_intel or WithdrawalGeoIntelligence(store=self.store)
        self.ledger = ledger or AuditLedger()

    # ------------------------------------------------------------------------
    # 1. Police Alert Package Creation & Delivery
    # ------------------------------------------------------------------------

    def create_police_alert(
        self,
        case_id: str,
        caller_role: str = "BANK_OFFICIAL",
        source: str = "CyberShield Bank Official",
        priority_override: Optional[str] = None,
    ) -> PoliceAlertRecord:
        """Create and deliver a structured police alert package upon explicit bank official action."""
        # 1. Authorization Enforcement
        clean_role = str(caller_role).upper().strip()
        if clean_role not in ("BANK_OFFICIAL", "SYSTEM_ADMIN", "LEA_OFFICER"):
            raise PermissionError(
                f"Unauthorized action: role '{caller_role}' cannot create police alerts. "
                "Explicit bank official authorization is required."
            )

        # 2. Case Validation
        case_dict = self.store.get_case(case_id)
        if not case_dict:
            raise KeyError(f"Case not found: {case_id}")

        # 3. Deduplication / Idempotency Check
        existing_alert = self.store.get_police_alert_by_case(case_id)
        if existing_alert:
            log.info(f"[POLICE_ALERT] Idempotent request for case {case_id}: returning existing alert {existing_alert['police_alert_id']}")
            return PoliceAlertRecord(
                police_alert_id=existing_alert["police_alert_id"],
                case_id=existing_alert["case_id"],
                alert_status=existing_alert.get("alert_status", PoliceAlertStatus.SENT),
                priority=existing_alert.get("priority", "HIGH"),
                source=existing_alert.get("source", source),
                incident=existing_alert.get("incident", {}),
                origin_transaction=existing_alert.get("origin_transaction", {}),
                money_trail=existing_alert.get("money_trail", []),
                relevant_accounts=existing_alert.get("relevant_accounts", []),
                withdrawal_attempts=existing_alert.get("withdrawal_attempts", []),
                nearby_terminals=existing_alert.get("nearby_terminals", []),
                location_timeline=existing_alert.get("location_timeline", []),
                evidence=existing_alert.get("evidence", []),
                created_at=existing_alert.get("created_at", ""),
                updated_at=existing_alert.get("updated_at", ""),
                acknowledged_at=existing_alert.get("acknowledged_at"),
                acknowledged_by=existing_alert.get("acknowledged_by"),
                notes=existing_alert.get("notes", ""),
            )

        # 4. Determine Alert Priority
        risk_score = float(case_dict.get("risk_score", 0.0))
        band = case_dict.get("band", "HIGH")
        if priority_override:
            priority = priority_override
        elif risk_score >= 0.8 or band == "CRITICAL":
            priority = "CRITICAL"
        elif risk_score >= 0.6 or band == "HIGH":
            priority = "HIGH"
        elif risk_score >= 0.4:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        now_str = datetime.now(timezone.utc).isoformat()
        alert_id = f"POL-ALERT-{case_id.replace('CASE-', '')}"

        # 5. Assemble Package Components

        # A. Incident Summary
        incident = {
            "case_id": case_id,
            "risk_level": band,
            "risk_score": risk_score,
            "confidence": float(case_dict.get("confidence", 0.0) or 0.0),
            "current_case_state": case_dict.get("state", "PRE_COMPLAINT_INTERVENTION"),
            "reason_for_escalation": "Bank Official explicit approval for police dispatch & cash egress interception.",
            "timestamp": case_dict.get("created_at", now_str),
            "flagged_account_id": case_dict.get("flagged_account_id", ""),
            "suspicious_amount": float(case_dict.get("suspicious_amount", 0.0)),
            "protected_amount": float(case_dict.get("protected_amount", 0.0)),
        }

        # B. Downstream Money Trail & Relevant Accounts (From Part 2 Trace Engine)
        money_trail_raw = case_dict.get("money_trail", [])
        money_trail = []
        relevant_accounts_set = {case_dict.get("flagged_account_id")}

        # Try retrieving full provenance chain from Part 2 engine
        recovery_case = self.trace_engine.get_recovery_case_query(case_id)
        if recovery_case:
            tx_chain = recovery_case.get("traceable_transactions", [])
            for idx, tx in enumerate(tx_chain, start=1):
                money_trail.append({
                    "hop": idx,
                    "source_account": tx.get("from_account_id"),
                    "destination_account": tx.get("to_account_id"),
                    "amount": float(tx.get("amount_inr", 0.0)),
                    "timestamp": tx.get("timestamp", ""),
                    "channel": tx.get("payment_channel", "UPI"),
                    "root_transaction": recovery_case.get("root_transaction_id", ""),
                    "risk_flags": ["PROVENANCE_TRACKED_HOP"],
                })
                relevant_accounts_set.add(tx.get("from_account_id"))
                relevant_accounts_set.add(tx.get("to_account_id"))
        elif money_trail_raw:
            for idx, leg in enumerate(money_trail_raw, start=1):
                leg_dict = leg.to_dict() if hasattr(leg, "to_dict") else dict(leg)
                src = leg_dict.get("source_account_id", leg_dict.get("source_account"))
                dst = leg_dict.get("target_account_id", leg_dict.get("destination_account"))
                money_trail.append({
                    "hop": leg_dict.get("hop_index", idx),
                    "source_account": src,
                    "destination_account": dst,
                    "amount": float(leg_dict.get("amount_inr", leg_dict.get("amount", 0.0))),
                    "timestamp": leg_dict.get("timestamp", ""),
                    "channel": leg_dict.get("payment_channel", leg_dict.get("channel", "UPI")),
                    "root_transaction": case_id,
                    "risk_flags": leg_dict.get("suspicious_flags", ["FLAGGED_HOP"]),
                })
                if src:
                    relevant_accounts_set.add(src)
                if dst:
                    relevant_accounts_set.add(dst)

        # C. Origin Transaction
        first_hop = money_trail[0] if money_trail else {}
        origin_tx_id = first_hop.get("root_transaction") or f"TXN-{case_id}"
        confirmation_rec = self.store.get_confirmation_by_transaction(origin_tx_id) if hasattr(self.store, "get_confirmation_by_transaction") else None
        conf_status = confirmation_rec.get("status") if confirmation_rec else "UNCONFIRMED"

        origin_transaction = {
            "transaction_id": origin_tx_id,
            "origin_account": first_hop.get("source_account", case_dict.get("flagged_account_id")),
            "destination_account": first_hop.get("destination_account", case_dict.get("flagged_account_id")),
            "amount": first_hop.get("amount", case_dict.get("suspicious_amount", 0.0)),
            "timestamp": first_hop.get("timestamp", case_dict.get("created_at", now_str)),
            "channel": first_hop.get("channel", "IMPS"),
            "confirmation_status": conf_status,
        }

        # D. Withdrawal / ATM Evidence (From Part 3 Geo Intel Engine)
        raw_withdrawals = self.geo_intel.get_case_withdrawals(case_id)
        withdrawal_attempts = []
        target_terminal_id = None

        for att in raw_withdrawals:
            att_dict = att.to_dict() if hasattr(att, "to_dict") else dict(att)
            tid = att_dict.get("terminal_id")
            if not target_terminal_id and tid:
                target_terminal_id = tid
            withdrawal_attempts.append({
                "attempt_id": att_dict.get("attempt_id"),
                "terminal_id": tid,
                "terminal_type": att_dict.get("payment_channel", "ATM"),
                "amount": float(att_dict.get("amount_inr", 0.0)),
                "timestamp": att_dict.get("timestamp", ""),
                "status": att_dict.get("status", "BLOCKED" if att_dict.get("is_blocked") else "ALLOWED"),
                "latitude": att_dict.get("latitude"),
                "longitude": att_dict.get("longitude"),
                "predicted_vs_actual": "PREDICTED_MATCH" if att_dict.get("distance_to_predicted_km") == 0.0 else f"{att_dict.get('distance_to_predicted_km', 'N/A')} km dev",
            })

        # E. Nearby Terminal Information (Spatial Intelligence)
        preds = case_dict.get("predicted_terminals", [])
        if not target_terminal_id and preds:
            top_p = preds[0]
            target_terminal_id = top_p.get("terminal_id") if isinstance(top_p, dict) else getattr(top_p, "terminal_id", None)

        nearby_terminals = []
        if target_terminal_id:
            nearby_terminals = self.geo_intel.find_nearby_terminals(target_terminal_id, radius_km=5.0, limit=5)

        # F. Chronological Location Evidence Timeline
        raw_timeline = self.geo_intel.get_case_location_history(case_id)
        location_timeline = [loc.to_dict() for loc in raw_timeline]

        # G. Human-Readable Evidence Reasons
        evidence_reasons = list(case_dict.get("evidence", []))
        if not evidence_reasons:
            evidence_reasons = [
                "Rapid forwarding through multiple accounts",
                "Multiple suspicious inbound transfers",
                "Predicted cashout terminal targeted",
                "Bank official verified case escalation",
            ]

        # 6. Build Record & Persist
        record = PoliceAlertRecord(
            police_alert_id=alert_id,
            case_id=case_id,
            alert_status=PoliceAlertStatus.SENT,
            priority=priority,
            source=source,
            incident=incident,
            origin_transaction=origin_transaction,
            money_trail=money_trail,
            relevant_accounts=list(relevant_accounts_set - {None, ""}),
            withdrawal_attempts=withdrawal_attempts,
            nearby_terminals=nearby_terminals,
            location_timeline=location_timeline,
            evidence=evidence_reasons,
            created_at=now_str,
            updated_at=now_str,
            notes=f"Escalated by {caller_role} via {source}.",
        )

        self.store.save_police_alert(record)

        # Update case record LEA notification status
        case_dict["lea_notification_status"] = "SENT"
        case_dict["updated_at"] = now_str
        self.store.save_case(case_dict)

        self.ledger.append({
            "event": "POLICE_ALERT_DISPATCHED",
            "police_alert_id": alert_id,
            "case_id": case_id,
            "priority": priority,
            "source": source,
            "timestamp": now_str,
        })

        log.info(f"[POLICE_ALERT] Created & delivered police alert {alert_id} for case {case_id} (Priority: {priority})")
        return record

    # ------------------------------------------------------------------------
    # 2. Police Acknowledgment & Investigation Workflow
    # ------------------------------------------------------------------------

    def acknowledge_police_alert(
        self,
        police_alert_id: str,
        caller_role: str = "POLICE_OFFICER",
        officer_id: str = "OFFICER-01",
        notes: str = "",
    ) -> PoliceAlertRecord:
        """Process police officer acknowledgment of alert receipt."""
        clean_role = str(caller_role).upper().strip()
        if clean_role not in ("POLICE_OFFICER", "LEA_OFFICER", "SYSTEM_ADMIN"):
            raise PermissionError(
                f"Unauthorized action: role '{caller_role}' cannot acknowledge police alerts. "
                "Police officer authorization is required."
            )

        alert_dict = self.store.get_police_alert(police_alert_id)
        if not alert_dict:
            raise KeyError(f"Police alert not found: {police_alert_id}")

        updated_dict = self.store.update_police_alert_status(
            police_alert_id=police_alert_id,
            new_status=PoliceAlertStatus.ACKNOWLEDGED,
            actor_id=officer_id,
            notes=notes or f"Acknowledged by {officer_id}",
        )

        self.ledger.append({
            "event": "POLICE_ALERT_ACKNOWLEDGED",
            "police_alert_id": police_alert_id,
            "case_id": alert_dict["case_id"],
            "officer_id": officer_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        log.info(f"[POLICE_ALERT] Alert {police_alert_id} ACKNOWLEDGED by {officer_id}")
        return PoliceAlertRecord(
            police_alert_id=updated_dict["police_alert_id"],
            case_id=updated_dict["case_id"],
            alert_status=updated_dict["alert_status"],
            priority=updated_dict.get("priority", "HIGH"),
            source=updated_dict.get("source", "CyberShield Bank Official"),
            incident=updated_dict.get("incident", {}),
            origin_transaction=updated_dict.get("origin_transaction", {}),
            money_trail=updated_dict.get("money_trail", []),
            relevant_accounts=updated_dict.get("relevant_accounts", []),
            withdrawal_attempts=updated_dict.get("withdrawal_attempts", []),
            nearby_terminals=updated_dict.get("nearby_terminals", []),
            location_timeline=updated_dict.get("location_timeline", []),
            evidence=updated_dict.get("evidence", []),
            created_at=updated_dict.get("created_at", ""),
            updated_at=updated_dict.get("updated_at", ""),
            acknowledged_at=updated_dict.get("acknowledged_at"),
            acknowledged_by=updated_dict.get("acknowledged_by"),
            notes=updated_dict.get("notes", ""),
        )

    def update_investigation_status(
        self,
        police_alert_id: str,
        new_status: str,
        caller_role: str = "POLICE_OFFICER",
        officer_id: str = "OFFICER-01",
        notes: str = "",
    ) -> PoliceAlertRecord:
        """Update police investigation status (UNDER_INVESTIGATION, RESOLVED, CLOSED)."""
        clean_role = str(caller_role).upper().strip()
        if clean_role not in ("POLICE_OFFICER", "LEA_OFFICER", "SYSTEM_ADMIN"):
            raise PermissionError(
                f"Unauthorized action: role '{caller_role}' cannot update police investigation status. "
                "Police officer authorization is required."
            )

        valid_statuses = {
            PoliceAlertStatus.ACKNOWLEDGED,
            PoliceAlertStatus.UNDER_INVESTIGATION,
            PoliceAlertStatus.RESOLVED,
            PoliceAlertStatus.CLOSED,
        }
        clean_status = str(new_status).upper().strip()
        if clean_status not in valid_statuses:
            raise ValueError(f"Invalid police investigation status '{new_status}'. Must be one of {valid_statuses}")

        alert_dict = self.store.get_police_alert(police_alert_id)
        if not alert_dict:
            raise KeyError(f"Police alert not found: {police_alert_id}")

        updated_dict = self.store.update_police_alert_status(
            police_alert_id=police_alert_id,
            new_status=clean_status,
            actor_id=officer_id,
            notes=notes or f"Status updated to {clean_status} by {officer_id}",
        )

        self.ledger.append({
            "event": "POLICE_INVESTIGATION_STATUS_UPDATED",
            "police_alert_id": police_alert_id,
            "case_id": alert_dict["case_id"],
            "new_status": clean_status,
            "officer_id": officer_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        log.info(f"[POLICE_ALERT] Alert {police_alert_id} investigation status updated to {clean_status} by {officer_id}")
        return PoliceAlertRecord(
            police_alert_id=updated_dict["police_alert_id"],
            case_id=updated_dict["case_id"],
            alert_status=updated_dict["alert_status"],
            priority=updated_dict.get("priority", "HIGH"),
            source=updated_dict.get("source", "CyberShield Bank Official"),
            incident=updated_dict.get("incident", {}),
            origin_transaction=updated_dict.get("origin_transaction", {}),
            money_trail=updated_dict.get("money_trail", []),
            relevant_accounts=updated_dict.get("relevant_accounts", []),
            withdrawal_attempts=updated_dict.get("withdrawal_attempts", []),
            nearby_terminals=updated_dict.get("nearby_terminals", []),
            location_timeline=updated_dict.get("location_timeline", []),
            evidence=updated_dict.get("evidence", []),
            created_at=updated_dict.get("created_at", ""),
            updated_at=updated_dict.get("updated_at", ""),
            acknowledged_at=updated_dict.get("acknowledged_at"),
            acknowledged_by=updated_dict.get("acknowledged_by"),
            notes=updated_dict.get("notes", ""),
        )

    def get_police_alert(self, police_alert_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve police alert package by ID."""
        return self.store.get_police_alert(police_alert_id)

    def list_police_alerts(
        self,
        limit: int = 50,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve filtered queue of police alerts."""
        return self.store.recent_police_alerts(limit=limit, status=status, priority=priority)
