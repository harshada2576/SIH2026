"""pipeline/integration_adapters.py — Institutional Integration Adapter Layer (SIH26184).

Provides standardized future-ready integration interface for Banks, Law Enforcement Agencies (LEA),
and I4C (Indian Cybercrime Coordination Centre).

Modes:
- "simulated" (default): Simulated execution over mock endpoints with data minimization and failure realism.
- "live": Production mode — raises NotImplementedError("Future integration: no live institutional connection").
"""
from __future__ import annotations

import abc
import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from audit.blockchain_lite import AuditLedger
from shared.schemas import CaseLifecycleState

log = logging.getLogger("integration_adapters")

INTEGRATION_MODE = os.getenv("INTEGRATION_MODE", "simulated").lower()


@dataclass
class StandardDispatchPayload:
    """Standardized institutional dispatch payload with role-based data minimization."""
    case_id: str
    idempotency_key: str
    risk_score: float
    simulated: bool = True
    reviewer_role: str = "BANK_OFFICIAL"
    reviewer_reason: str = "Authorized by human reviewer"
    recommended_action: str = "BANK_HOLD"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseInstitutionAdapter(abc.ABC):
    """Abstract Base Class for all institutional connector adapters."""

    def __init__(self, name: str, simulated: bool = True) -> None:
        self.name = name
        self.simulated = simulated
        self._dispatched_keys: set[str] = set()

    def check_mode(self) -> None:
        """Enforce strict guard against fake live claims."""
        mode = os.getenv("INTEGRATION_MODE", "simulated").lower()
        if mode == "live":
            raise NotImplementedError(
                f"Future integration: no live institutional connection configured for {self.name}."
            )

    @abc.abstractmethod
    def send_alert(self, case: Dict[str, Any], reviewer_role: str, reason: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Dispatch high-priority risk alert to institution."""
        pass

    @abc.abstractmethod
    def request_hold(self, case: Dict[str, Any], reviewer_role: str, reason: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Request digital fund hold or account freeze."""
        pass

    @abc.abstractmethod
    def share_intel(self, case: Dict[str, Any], reviewer_role: str, reason: str) -> Dict[str, Any]:
        """Share anonymized cybercrime intelligence payload."""
        pass

    @abc.abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return connector operational health status."""
        pass


class SimulatedBankAdapter(BaseInstitutionAdapter):
    """Simulated Bank Core API Adapter with data minimization (account & hold delta only)."""

    def __init__(self, simulate_transient_failure: bool = False) -> None:
        super().__init__(name="Simulated Bank Core Adapter", simulated=True)
        self.simulate_transient_failure = simulate_transient_failure

    def send_alert(self, case: Dict[str, Any], reviewer_role: str, reason: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        self.check_mode()
        if not reason or not reason.strip():
            raise ValueError("Human review reason must be non-empty prior to dispatch.")

        ikey = idempotency_key or f"BANK-ALT-{case['ncrpId']}-{uuid.uuid4().hex[:6]}"
        if ikey in self._dispatched_keys:
            return {"status": "ALREADY_DISPATCHED", "idempotency_key": ikey, "simulated": True}

        if self.simulate_transient_failure:
            return {"status": "FAILED", "error": "Simulated bank gateway timeout", "simulated": True, "retryable": True}

        self._dispatched_keys.add(ikey)

        # Data Minimization: Bank gets account ID and exposure amount only
        minimized = {
            "account_id": case.get("flaggedAccountId") or case.get("victimAccount"),
            "hold_amount_inr": case.get("suspiciousExposure", 0.0),
            "bank_action": "HOLD_REQUESTED",
        }

        payload = StandardDispatchPayload(
            case_id=case["ncrpId"],
            idempotency_key=ikey,
            risk_score=float(case.get("riskScore", 0.85)),
            simulated=True,
            reviewer_role=reviewer_role,
            reviewer_reason=reason,
            recommended_action="BANK_HOLD",
            payload_data=minimized,
        )

        return {"status": "SENT", "connector": self.name, "payload": payload.to_dict(), "simulated": True}

    def request_hold(self, case: Dict[str, Any], reviewer_role: str, reason: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return self.send_alert(case, reviewer_role, reason, idempotency_key)

    def share_intel(self, case: Dict[str, Any], reviewer_role: str, reason: str) -> Dict[str, Any]:
        self.check_mode()
        return {"status": "INTEL_SHARED", "connector": self.name, "simulated": True}

    def get_status(self) -> Dict[str, Any]:
        mode = os.getenv("INTEGRATION_MODE", "simulated").lower()
        return {
            "connector": self.name,
            "mode": mode,
            "roadmap_state": "Interface Ready / Simulated",
            "simulated": True,
            "healthy": mode != "live",
        }


class SimulatedLEAAdapter(BaseInstitutionAdapter):
    """Simulated Law Enforcement Agency (LEA) Adapter with data minimization (coordinates & terminals)."""

    def __init__(self, simulate_transient_failure: bool = False) -> None:
        super().__init__(name="Simulated Police LEA Dispatcher", simulated=True)
        self.simulate_transient_failure = simulate_transient_failure

    def send_alert(self, case: Dict[str, Any], reviewer_role: str, reason: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        self.check_mode()
        if not reason or not reason.strip():
            raise ValueError("Human review reason must be non-empty prior to police dispatch.")

        # Guard: Cannot dispatch dismissed or unapproved case
        state = case.get("status") or case.get("lifecycle")
        if state in ("DISMISSED_FALSE_POSITIVE", "PENDING_CONFIRMATION"):
            raise PermissionError(f"Cannot dispatch case in state '{state}' to Police/LEA.")

        ikey = idempotency_key or f"LEA-ALT-{case['ncrpId']}-{uuid.uuid4().hex[:6]}"
        if ikey in self._dispatched_keys:
            return {"status": "ALREADY_DISPATCHED", "idempotency_key": ikey, "simulated": True}

        if self.simulate_transient_failure:
            return {"status": "FAILED", "error": "Simulated LEA portal unreachable", "simulated": True, "retryable": True}

        self._dispatched_keys.add(ikey)

        target = case.get("targetTerminal") or {}
        minimized = {
            "target_terminal_id": target.get("id"),
            "location_address": target.get("address"),
            "latitude": target.get("latitude"),
            "longitude": target.get("longitude"),
            "cashout_window": target.get("cashoutWindow"),
            "case_summary": case.get("summary"),
        }

        payload = StandardDispatchPayload(
            case_id=case["ncrpId"],
            idempotency_key=ikey,
            risk_score=float(case.get("riskScore", 0.90)),
            simulated=True,
            reviewer_role=reviewer_role,
            reviewer_reason=reason,
            recommended_action="DISPATCH_PATROL",
            payload_data=minimized,
        )

        return {"status": "SENT", "connector": self.name, "payload": payload.to_dict(), "simulated": True}

    def request_hold(self, case: Dict[str, Any], reviewer_role: str, reason: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return self.send_alert(case, reviewer_role, reason, idempotency_key)

    def share_intel(self, case: Dict[str, Any], reviewer_role: str, reason: str) -> Dict[str, Any]:
        self.check_mode()
        return {"status": "INTEL_SHARED", "connector": self.name, "simulated": True}

    def get_status(self) -> Dict[str, Any]:
        mode = os.getenv("INTEGRATION_MODE", "simulated").lower()
        return {
            "connector": self.name,
            "mode": mode,
            "roadmap_state": "Interface Ready / Simulated",
            "simulated": True,
            "healthy": mode != "live",
        }


class SimulatedI4CAdapter(BaseInstitutionAdapter):
    """Simulated I4C / NCRP Portal Adapter with data minimization (case summary & cryptographic evidence hash)."""

    def __init__(self, simulate_transient_failure: bool = False) -> None:
        super().__init__(name="Simulated I4C / NCRP Gateway", simulated=True)
        self.simulate_transient_failure = simulate_transient_failure

    def send_alert(self, case: Dict[str, Any], reviewer_role: str, reason: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        self.check_mode()
        if not reason or not reason.strip():
            raise ValueError("Human review reason must be non-empty prior to I4C notification.")

        ikey = idempotency_key or f"I4C-ALT-{case['ncrpId']}-{uuid.uuid4().hex[:6]}"
        if ikey in self._dispatched_keys:
            return {"status": "ALREADY_DISPATCHED", "idempotency_key": ikey, "simulated": True}

        if self.simulate_transient_failure:
            return {"status": "FAILED", "error": "Simulated I4C API timeout", "simulated": True, "retryable": True}

        self._dispatched_keys.add(ikey)

        ev_list = case.get("evidence", [])
        ev_hash = hashlib.sha256(json.dumps(ev_list).encode("utf-8")).hexdigest()

        minimized = {
            "ncrp_complaint_id": case.get("complaintId") or case.get("ncrpId"),
            "evidence_hash": ev_hash,
            "involved_accounts_count": len(case.get("evidence", [])),
            "threat_category": "PREDICTIVE_EGRESS_MULE_CHAIN",
        }

        payload = StandardDispatchPayload(
            case_id=case["ncrpId"],
            idempotency_key=ikey,
            risk_score=float(case.get("riskScore", 0.88)),
            simulated=True,
            reviewer_role=reviewer_role,
            reviewer_reason=reason,
            recommended_action="INDEX_NCRP_INCIDENT",
            payload_data=minimized,
        )

        return {"status": "SENT", "connector": self.name, "payload": payload.to_dict(), "simulated": True}

    def request_hold(self, case: Dict[str, Any], reviewer_role: str, reason: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        return self.send_alert(case, reviewer_role, reason, idempotency_key)

    def share_intel(self, case: Dict[str, Any], reviewer_role: str, reason: str) -> Dict[str, Any]:
        self.check_mode()
        return {"status": "INTEL_SHARED", "connector": self.name, "simulated": True}

    def get_status(self) -> Dict[str, Any]:
        mode = os.getenv("INTEGRATION_MODE", "simulated").lower()
        return {
            "connector": self.name,
            "mode": mode,
            "roadmap_state": "Interface Ready / Simulated",
            "simulated": True,
            "healthy": mode != "live",
        }


class InstitutionalIntegrationManager:
    """Orchestrates human-in-the-loop review dispatches across Bank, LEA, and I4C adapters."""

    def __init__(self, ledger: Optional[AuditLedger] = None) -> None:
        self.ledger = ledger or AuditLedger()
        self.bank_adapter = SimulatedBankAdapter()
        self.lea_adapter = SimulatedLEAAdapter()
        self.i4c_adapter = SimulatedI4CAdapter()

    def dispatch_case_decision(
        self,
        case: Dict[str, Any],
        action: str,
        reviewer_role: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Dispatch case decision with mandatory human review reason, logging to hash-chained Ed25519 audit ledger."""
        if not reason or not reason.strip():
            raise ValueError("Human review reason is required for institutional dispatch.")

        mode = os.getenv("INTEGRATION_MODE", "simulated").lower()
        if mode == "live":
            raise NotImplementedError("Future integration: no live institutional connection configured.")

        # Execute dispatches across institutional connectors
        b_res = self.bank_adapter.send_alert(case, reviewer_role, reason)
        l_res = self.lea_adapter.send_alert(case, reviewer_role, reason)
        i_res = self.i4c_adapter.send_alert(case, reviewer_role, reason)

        dispatch_record = {
            "event_type": "INSTITUTIONAL_DISPATCH",
            "ncrp_id": case["ncrpId"],
            "action": action,
            "adapter_mode": mode,
            "reviewer_role": reviewer_role,
            "reason": reason,
            "simulated": True,
            "dispatches": {
                "bank": b_res["status"],
                "lea": l_res["status"],
                "i4c": i_res["status"],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Log to hash-chained Ed25519 audit ledger
        block = self.ledger.append(dispatch_record)

        return {
            "status": "DISPATCH_COMPLETED",
            "case_id": case["ncrpId"],
            "simulated": True,
            "mode": mode,
            "audit_block_hash": block.hash,
            "dispatches": [b_res, l_res, i_res],
        }

    def get_connector_statuses(self) -> Dict[str, Any]:
        mode = os.getenv("INTEGRATION_MODE", "simulated").lower()
        return {
            "mode": mode,
            "simulated": True,
            "roadmap_state": "Interface Ready / Simulated (Live: Future)",
            "connectors": [
                self.bank_adapter.get_status(),
                self.lea_adapter.get_status(),
                self.i4c_adapter.get_status(),
            ],
        }
