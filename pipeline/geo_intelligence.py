"""pipeline/geo_intelligence.py — Withdrawal & Geo Intelligence Layer for SIH26184.

Answers: “When a marked account attempts to cash out, where did it happen, when did it happen,
which terminal was involved, and what nearby locations should investigators/police be aware of?”

Key Mandates:
1. Structured Withdrawal Attempt Processing: attempt_id, account_id, terminal_id, amount, timestamp,
   lat/long, channel, status (ALLOWED, BLOCKED, INTERCEPTED, FLAGGED), case_id.
2. Marked Account Intervention: Integrates with existing transaction-control / selective hold layers.
3. Predicted Terminal Correlation: Computes exact match or spatial deviation from predicted cash-out ATMs.
4. Nearby Spatial Intelligence: Discovers and ranks alternative egress terminals using Haversine distance.
5. Chronological Location History: Compiles structured location evidence for CyberShield and LEA.
6. Repeated Account <-> Terminal Targeting: Tracks recurrence and escalates risk tiers:
   - 1 attempt  -> MONITORED (1.0x)
   - 2 attempts -> ELEVATED_RISK (1.25x)
   - 3+         -> PERSISTENT_TERMINAL_RISK (1.5x)
7. Complete Persistence & Idempotency: Backed by SQLite Store.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Union

from audit.blockchain_lite import AuditLedger
from pipeline.graph_store import GraphStore, _as_utc
from shared.persistence import Store
from shared.schemas import (
    ConfirmationStatus,
    LocationEvidenceRecord,
    TransactionChannel,
    WithdrawalAttemptEvent,
    _format_iso,
)

log = logging.getLogger("geo_intelligence")


class WithdrawalGeoIntelligence:
    """Manages cash-out attempts, spatial proximity calculations, and location intelligence."""

    def __init__(
        self,
        store: Optional[Store] = None,
        graph_store: Optional[GraphStore] = None,
        ledger: Optional[AuditLedger] = None,
    ) -> None:
        self.store = store or Store()
        self.graph_store = graph_store or GraphStore()
        self.ledger = ledger or AuditLedger()

    # ------------------------------------------------------------------------
    # 1. Withdrawal Attempt Ingestion & Intervention
    # ------------------------------------------------------------------------

    def process_withdrawal_attempt(
        self,
        attempt_id: str,
        account_id: str,
        terminal_id: str,
        amount_inr: float,
        timestamp: Optional[Union[str, datetime]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        payment_channel: str = "ATM",
        case_id: Optional[str] = None,
        existing_balance: float = 20000.0,
    ) -> WithdrawalAttemptEvent:
        """Process a withdrawal attempt, apply channel/hold intervention, correlate with case, and log geo-intel."""
        ts_dt = _as_utc(timestamp) if timestamp is not None else datetime.now(timezone.utc)
        ts_str = _format_iso(ts_dt)

        # Idempotency check: if attempt_id already persisted, return existing record
        existing_attempt = self.store.get_withdrawal_attempt(attempt_id) if hasattr(self.store, "get_withdrawal_attempt") else None
        if existing_attempt:
            return WithdrawalAttemptEvent(
                attempt_id=existing_attempt["attempt_id"],
                terminal_id=existing_attempt["terminal_id"],
                account_id=existing_attempt["account_id"],
                amount_inr=float(existing_attempt["amount_inr"]),
                timestamp=existing_attempt.get("timestamp", ts_str),
                latitude=existing_attempt.get("latitude"),
                longitude=existing_attempt.get("longitude"),
                payment_channel=existing_attempt.get("payment_channel", payment_channel),
                correlated_case_id=existing_attempt.get("correlated_case_id"),
                is_blocked=bool(existing_attempt.get("is_blocked", False)),
                action_taken=existing_attempt.get("action_taken", "MONITORED"),
                status=existing_attempt.get("status", "ALLOWED"),
                reason=existing_attempt.get("reason"),
                distance_to_predicted_km=existing_attempt.get("distance_to_predicted_km"),
                nearby_terminals=existing_attempt.get("nearby_terminals", []),
            )

        # 1. Resolve terminal static coordinates
        term_meta = self.graph_store.terminals.get(str(terminal_id), {})
        t_lat = latitude if latitude is not None else term_meta.get("latitude")
        t_lon = longitude if longitude is not None else term_meta.get("longitude")
        if t_lat is not None:
            t_lat = float(t_lat)
        if t_lon is not None:
            t_lon = float(t_lon)

        # 2. Correlate with active case and compute distance to predicted terminal
        matched_case_id = case_id
        distance_to_pred: Optional[float] = None
        top_predicted_terminal: Optional[str] = None
        correlated_case_dict: Optional[Dict[str, Any]] = None

        if case_id and hasattr(self.store, "get_case"):
            correlated_case_dict = self.store.get_case(case_id)
            if correlated_case_dict:
                matched_case_id = correlated_case_dict["case_id"]

        if not correlated_case_dict:
            active_cases = self.store.recent_cases(limit=50) if hasattr(self.store, "recent_cases") else []
            for c in active_cases:
                if case_id and c.get("case_id") == case_id:
                    correlated_case_dict = c
                    matched_case_id = c["case_id"]
                    break
                if c.get("flagged_account_id") == account_id:
                    correlated_case_dict = c
                    matched_case_id = c["case_id"]
                    break

        if correlated_case_dict:
            preds = correlated_case_dict.get("predicted_terminals", [])
            if preds:
                top_pred = preds[0]
                top_pred_id = top_pred.get("terminal_id") if isinstance(top_pred, dict) else getattr(top_pred, "terminal_id", None)
                top_predicted_terminal = top_pred_id
                if top_pred_id == terminal_id:
                    distance_to_pred = 0.0
                else:
                    p_lat = top_pred.get("latitude") if isinstance(top_pred, dict) else getattr(top_pred, "latitude", None)
                    p_lon = top_pred.get("longitude") if isinstance(top_pred, dict) else getattr(top_pred, "longitude", None)
                    if p_lat is not None and p_lon is not None and t_lat is not None and t_lon is not None:
                        distance_to_pred = self._compute_haversine(t_lat, t_lon, float(p_lat), float(p_lon))

        # 3. Determine intervention state (Active terminal blocks or account holds)
        is_blocked = False
        action_taken = "ALLOWED"
        status = "ALLOWED"
        reason = "Clean standard withdrawal"

        # A. Check terminal hardware blocks
        active_term_blocks = self.store.get_active_terminal_blocks(terminal_id)
        if active_term_blocks:
            is_blocked = True
            action_taken = "BLOCKED"
            status = "BLOCKED"
            reason = f"Withdrawal intercepted: physical block active on terminal {terminal_id} (Reason: {active_term_blocks[0].get('reason', 'PREDICTED_CASH_EGRESS')})"

        # B. Check account holds / pending confirmations / confirmed fraud
        if not is_blocked:
            # Check pending confirmations
            pending_confs = self.store.get_pending_confirmations()
            rel_pending = next((p for p in pending_confs if p.get("destination_account_id") == account_id), None)

            # Check confirmed fraud
            all_confs = self.store.recent_confirmations(limit=100)
            is_confirmed_fraud = any(
                c.get("status") == ConfirmationStatus.CONFIRMED_FRAUD and c.get("destination_account_id") == account_id
                for c in all_confs
            )

            # Check account exposure
            acc_exp = self.store.get_account_exposure(account_id)
            suspicious_exp = float(acc_exp.get("suspicious_exposure", 0.0)) if acc_exp else 0.0
            legit_bal = float(acc_exp.get("legitimate_balance", existing_balance)) if acc_exp else existing_balance

            if is_confirmed_fraud:
                is_blocked = True
                action_taken = "BLOCKED"
                status = "BLOCKED"
                reason = f"Withdrawal blocked: account {account_id} is subject to confirmed fraud recovery freeze."
            elif rel_pending:
                susp_amt = float(rel_pending.get("amount_inr", 0.0))
                if amount_inr > legit_bal:
                    is_blocked = True
                    action_taken = "INTERCEPTED"
                    status = "INTERCEPTED"
                    reason = (
                        f"Withdrawal of ₹{amount_inr:,.2f} intercepted: exceeds legitimate balance (₹{legit_bal:,.2f}) "
                        f"and touches provisional funds (₹{susp_amt:,.2f}) under {rel_pending.get('status')}."
                    )
                else:
                    action_taken = "ALLOWED"
                    status = "ALLOWED"
                    reason = f"Withdrawal of ₹{amount_inr:,.2f} permitted from pre-existing legitimate balance (₹{legit_bal:,.2f})."
            elif correlated_case_dict and correlated_case_dict.get("bank_hold_status") in ("ACTIVE", "FULL_FREEZE"):
                is_blocked = True
                action_taken = "BLOCKED"
                status = "BLOCKED"
                reason = f"Withdrawal blocked: statutory multi-agency freeze active on account {account_id}."

        # 4. Find nearby terminals
        nearby_terminals = self.find_nearby_terminals(terminal_id, radius_km=5.0, limit=5)

        # 5. Record repeated targeting
        recurrence = self.graph_store.record_account_terminal_activity(account_id, terminal_id, ts_dt)

        attempt_event = WithdrawalAttemptEvent(
            attempt_id=attempt_id,
            terminal_id=terminal_id,
            account_id=account_id,
            amount_inr=float(amount_inr),
            timestamp=ts_dt,
            latitude=t_lat,
            longitude=t_lon,
            payment_channel=payment_channel,
            correlated_case_id=matched_case_id,
            is_blocked=is_blocked,
            action_taken=action_taken,
            status=status,
            reason=reason,
            distance_to_predicted_km=distance_to_pred,
            nearby_terminals=nearby_terminals,
        )

        # Save to SQLite
        self.store.save_withdrawal_attempt(attempt_event)

        # Append to case withdrawal attempts list in store if correlated
        if matched_case_id and correlated_case_dict:
            attempts_list = list(correlated_case_dict.get("withdrawal_attempts", []))
            attempts_list.append(attempt_event.to_dict())
            correlated_case_dict["withdrawal_attempts"] = attempts_list
            correlated_case_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
            if correlated_case_dict.get("state") == "PRE_COMPLAINT_INTERVENTION":
                correlated_case_dict["state"] = "CASHOUT_ATTEMPT_DETECTED"
            self.store.save_case(correlated_case_dict)

        self.ledger.append({
            "event": "WITHDRAWAL_ATTEMPT_PROCESSED",
            "attempt_id": attempt_id,
            "account_id": account_id,
            "terminal_id": terminal_id,
            "amount_inr": amount_inr,
            "status": status,
            "is_blocked": is_blocked,
            "correlated_case_id": matched_case_id,
            "distance_to_predicted_km": distance_to_pred,
            "escalation_state": recurrence.get("escalation_state"),
        })

        log.info(f"[GEO_INTEL] Processed withdrawal {attempt_id} at {terminal_id} by {account_id} for ₹{amount_inr:,.2f} -> {status} ({reason})")
        return attempt_event

    # ------------------------------------------------------------------------
    # 2. Nearby Spatial Intelligence
    # ------------------------------------------------------------------------

    def find_nearby_terminals(
        self,
        terminal_id: str,
        radius_km: float = 5.0,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find other terminals within radius_km using Haversine distance."""
        base = self.graph_store.terminals.get(str(terminal_id))
        if not base or "latitude" not in base or "longitude" not in base:
            return []

        b_lat, b_lon = float(base["latitude"]), float(base["longitude"])
        results = []

        for tid, term in self.graph_store.terminals.items():
            if tid == terminal_id:
                continue
            lat = term.get("latitude")
            lon = term.get("longitude")
            if lat is None or lon is None:
                continue

            dist = self._compute_haversine(b_lat, b_lon, float(lat), float(lon))
            if dist <= radius_km:
                results.append({
                    "terminal_id": tid,
                    "terminal_type": term.get("terminal_type", "ATM_KIOSK"),
                    "district": term.get("district", ""),
                    "district_pincode": term.get("district_pincode", term.get("pincode", "")),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "distance_km": dist,
                })

        results.sort(key=lambda x: x["distance_km"])
        return results[:limit]

    def _compute_haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate Haversine distance in kilometers between two lat/long points."""
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return round(6371.0 * c, 2)

    # ------------------------------------------------------------------------
    # 3. Location History & LEA Evidence
    # ------------------------------------------------------------------------

    def get_case_location_history(self, case_id: str) -> List[LocationEvidenceRecord]:
        """Compile structured chronological location history (predicted + actual recorded events) for a case."""
        case_dict = self.store.get_case(case_id) if hasattr(self.store, "get_case") else None
        history: List[LocationEvidenceRecord] = []

        if not case_dict:
            # Fallback to querying withdrawal attempts matching case_id
            attempts = self.store.get_withdrawal_attempts(limit=50)
            case_attempts = [a for a in attempts if a.get("correlated_case_id") == case_id]
            for a in case_attempts:
                tid = a["terminal_id"]
                term_meta = self.graph_store.terminals.get(tid, {})
                history.append(
                    LocationEvidenceRecord(
                        case_id=case_id,
                        terminal_id=tid,
                        terminal_type=term_meta.get("terminal_type", "ATM_KIOSK"),
                        district=term_meta.get("district", ""),
                        district_pincode=term_meta.get("district_pincode", term_meta.get("pincode", "")),
                        latitude=float(term_meta.get("latitude", 0.0)),
                        longitude=float(term_meta.get("longitude", 0.0)),
                        timestamp=a.get("timestamp", ""),
                        event_type="RECORDED_WITHDRAWAL",
                        amount_inr=float(a.get("amount_inr", 0.0)),
                        action_taken=a.get("action_taken", "MONITORED"),
                        status="BLOCKED" if a.get("is_blocked") else "ALLOWED",
                        distance_from_predicted_km=a.get("distance_to_predicted_km"),
                    )
                )
            return sorted(history, key=lambda x: x.timestamp)

        # 1. Add Predicted Terminal Locations
        for pred in case_dict.get("predicted_terminals", []):
            tid = pred.get("terminal_id", "")
            term_meta = self.graph_store.terminals.get(tid, {})
            history.append(
                LocationEvidenceRecord(
                    case_id=case_id,
                    terminal_id=tid,
                    terminal_type=term_meta.get("terminal_type", "ATM_KIOSK"),
                    district=term_meta.get("district", ""),
                    district_pincode=term_meta.get("district_pincode", term_meta.get("pincode", "")),
                    latitude=float(pred.get("latitude") or term_meta.get("latitude") or 0.0),
                    longitude=float(pred.get("longitude") or term_meta.get("longitude") or 0.0),
                    timestamp=case_dict.get("predicted_window_start", datetime.now(timezone.utc).isoformat()),
                    event_type="PREDICTED_EGRESS",
                    amount_inr=float(case_dict.get("suspicious_amount", 0.0)),
                    action_taken="PREDICTION",
                    status="PREDICTED",
                    distance_from_predicted_km=0.0,
                )
            )

        # 2. Add Recorded Withdrawal Attempts
        for att in case_dict.get("withdrawal_attempts", []):
            tid = att.get("terminal_id", "")
            term_meta = self.graph_store.terminals.get(tid, {})
            history.append(
                LocationEvidenceRecord(
                    case_id=case_id,
                    terminal_id=tid,
                    terminal_type=term_meta.get("terminal_type", "ATM_KIOSK"),
                    district=term_meta.get("district", ""),
                    district_pincode=term_meta.get("district_pincode", term_meta.get("pincode", "")),
                    latitude=float(term_meta.get("latitude") or att.get("latitude") or 0.0),
                    longitude=float(term_meta.get("longitude") or att.get("longitude") or 0.0),
                    timestamp=att.get("timestamp", ""),
                    event_type="RECORDED_WITHDRAWAL",
                    amount_inr=float(att.get("amount_inr", 0.0)),
                    action_taken=att.get("action_taken", "MONITORED"),
                    status="BLOCKED" if att.get("is_blocked") else "ALLOWED",
                    distance_from_predicted_km=att.get("distance_to_predicted_km"),
                )
            )

        return sorted(history, key=lambda x: x.timestamp)

    # ------------------------------------------------------------------------
    # 4. Repeated Account <-> Terminal Activity Tracking
    # ------------------------------------------------------------------------

    def get_account_terminal_history(
        self,
        account_id: str,
        terminal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve historical cash-out activity and escalation state for an account at terminals."""
        usages = self.graph_store.recent_terminal_usages(account_id, limit=50)
        attempts = self.store.get_withdrawal_attempts(account_id=account_id, terminal_id=terminal_id, limit=50)

        matching_usages = [u for u in usages if terminal_id is None or u["terminal_id"] == str(terminal_id)]
        count = len(matching_usages)

        if count >= 3:
            escalation_state = "PERSISTENT_TERMINAL_RISK"
            risk_multiplier = 1.5
            recommended_action = "ESCALATE_TERMINAL_BLOCK"
        elif count == 2:
            escalation_state = "ELEVATED_RISK"
            risk_multiplier = 1.25
            recommended_action = "ELEVATE_MONITORING"
        else:
            escalation_state = "MONITORED"
            risk_multiplier = 1.0
            recommended_action = "INITIAL_MONITOR"

        return {
            "account_id": account_id,
            "terminal_id": terminal_id,
            "attempt_count": count,
            "escalation_state": escalation_state,
            "risk_multiplier": risk_multiplier,
            "recommended_action": recommended_action,
            "recorded_attempts": attempts,
        }

    def get_case_withdrawals(self, case_id: str) -> List[Dict[str, Any]]:
        """Retrieve all withdrawal attempts associated with an investigation case."""
        case_dict = self.store.get_case(case_id) if hasattr(self.store, "get_case") else None
        if case_dict and case_dict.get("withdrawal_attempts"):
            return case_dict["withdrawal_attempts"]

        all_attempts = self.store.get_withdrawal_attempts(limit=100)
        return [a for a in all_attempts if a.get("correlated_case_id") == case_id]
