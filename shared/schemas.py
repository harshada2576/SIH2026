"""The 4 JSON schemas from Architecture.md section 6 — the shared contract.

All 3 workstreams import this one file; do not redefine these locally.
Changes to any field MUST be posted in the group chat BEFORE building against them.

Provides strongly-typed schemas with runtime validation for:
1. TransactionEvent (topic: "transactions")
2. GraphSignal (topic: "graph_signals" / internal graph updates)
3. RiskAlert (topic: "risk_alerts")
4. AccountNodeMetadata / AccountNode & TerminalNode (reference data)
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union


class ValidationError(ValueError):
    """Raised when a schema validation fails or a dictionary payload is malformed."""
    pass


def _as_utc_datetime(value: Union[str, datetime]) -> datetime:
    """Normalize a datetime or ISO string to UTC aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        clean_ts = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(clean_ts)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f"):
                try:
                    dt = datetime.strptime(value.replace("Z", ""), fmt)
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            raise ValidationError(f"Unrecognized datetime string format: '{value}'")
    raise ValidationError(f"Expected datetime or str, got: {type(value)}")


def _format_iso(value: Union[str, datetime]) -> str:
    """Format a datetime or string to ISO-8601 UTC string."""
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


# ============================================================================
# 1. TRANSACTION EVENT (Architecture.md §6.1)
# ============================================================================

VALID_PAYMENT_CHANNELS = {"UPI", "IMPS", "NEFT", "RTGS", "AEPS"}
ACCOUNT_ID_REGEX = re.compile(r"^ACC-[A-Za-z0-9_]+$")


@dataclass
class TransactionEvent:
    """One payment leg between two accounts (schema 6.1, topic 'transactions')."""

    transaction_id: str
    source_account_id: str
    target_account_id: str
    amount_inr: float
    timestamp: Union[str, datetime]
    payment_channel: str
    device_fingerprint: str

    def __post_init__(self):
        self.transaction_id = str(self.transaction_id)
        self.source_account_id = str(self.source_account_id)
        self.target_account_id = str(self.target_account_id)

        # Validate source & target format
        if not ACCOUNT_ID_REGEX.match(self.source_account_id) and not self.source_account_id.startswith("ACC"):
            raise ValidationError(f"Invalid source_account_id: '{self.source_account_id}'")
        if not ACCOUNT_ID_REGEX.match(self.target_account_id) and not self.target_account_id.startswith("ACC"):
            raise ValidationError(f"Invalid target_account_id: '{self.target_account_id}'")

        try:
            self.amount_inr = float(self.amount_inr)
        except (ValueError, TypeError):
            raise ValidationError(f"TransactionEvent.amount_inr must be float, got: {type(self.amount_inr)}")

        if self.amount_inr <= 0:
            raise ValidationError(f"TransactionEvent.amount_inr must be positive (> 0), got: {self.amount_inr}")

        if self.payment_channel not in VALID_PAYMENT_CHANNELS:
            raise ValidationError(
                f"Invalid payment_channel: '{self.payment_channel}'. Must be one of {VALID_PAYMENT_CHANNELS}"
            )

        self.device_fingerprint = str(self.device_fingerprint)

    @property
    def timestamp_utc(self) -> datetime:
        """UTC-normalized timestamp used by graph and rules."""
        return _as_utc_datetime(self.timestamp)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionEvent":
        required = [
            "transaction_id",
            "source_account_id",
            "target_account_id",
            "amount_inr",
            "timestamp",
            "payment_channel",
            "device_fingerprint",
        ]
        for field_name in required:
            if field_name not in data:
                raise ValidationError(f"Missing required field in TransactionEvent: '{field_name}'")

        return cls(
            transaction_id=data["transaction_id"],
            source_account_id=data["source_account_id"],
            target_account_id=data["target_account_id"],
            amount_inr=data["amount_inr"],
            timestamp=data["timestamp"],
            payment_channel=data["payment_channel"],
            device_fingerprint=data["device_fingerprint"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "source_account_id": self.source_account_id,
            "target_account_id": self.target_account_id,
            "amount_inr": self.amount_inr,
            "timestamp": _format_iso(self.timestamp),
            "payment_channel": self.payment_channel,
            "device_fingerprint": self.device_fingerprint,
        }


# ============================================================================
# 2. GRAPH SIGNAL (Pipeline Intermediate Topic Contract)
# ============================================================================

@dataclass
class GraphSignal:
    """Intermediate graph signal event emitted after updating GraphStore."""

    account_id: str
    timestamp: str
    fan_in_count: int
    fan_out_count: int
    distinct_counterparties: int
    shared_device_accounts: List[str] = field(default_factory=list)
    chain_depth: int = 0
    historical_terminal_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.shared_device_accounts, list):
            raise ValidationError("GraphSignal.shared_device_accounts must be a list")
        if not isinstance(self.historical_terminal_ids, list):
            raise ValidationError("GraphSignal.historical_terminal_ids must be a list")
        try:
            self.fan_in_count = int(self.fan_in_count)
            self.fan_out_count = int(self.fan_out_count)
            self.distinct_counterparties = int(self.distinct_counterparties)
            self.chain_depth = int(self.chain_depth)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"GraphSignal numeric fields must be integers: {e}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphSignal":
        required = [
            "account_id",
            "timestamp",
            "fan_in_count",
            "fan_out_count",
            "distinct_counterparties",
            "shared_device_accounts",
            "chain_depth",
            "historical_terminal_ids",
        ]
        for field_name in required:
            if field_name not in data:
                raise ValidationError(f"Missing required field in GraphSignal: '{field_name}'")

        if not isinstance(data.get("shared_device_accounts"), list):
            raise ValidationError("shared_device_accounts must be a list")
        if not isinstance(data.get("historical_terminal_ids"), list):
            raise ValidationError("historical_terminal_ids must be a list")

        return cls(
            account_id=str(data["account_id"]),
            timestamp=str(data["timestamp"]),
            fan_in_count=int(data["fan_in_count"]),
            fan_out_count=int(data["fan_out_count"]),
            distinct_counterparties=int(data["distinct_counterparties"]),
            shared_device_accounts=[str(x) for x in data["shared_device_accounts"]],
            chain_depth=int(data["chain_depth"]),
            historical_terminal_ids=[str(x) for x in data["historical_terminal_ids"]],
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# 3. RISK ALERT (Architecture.md §6.4)
# ============================================================================

@dataclass
class PredictedTerminal:
    """One ranked cash-out candidate inside a RiskAlert (schema 6.4)."""

    terminal_id: str
    probability: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def __post_init__(self):
        self.terminal_id = str(self.terminal_id)
        try:
            self.probability = float(self.probability)
        except (ValueError, TypeError):
            raise ValidationError(f"PredictedTerminal.probability must be float, got: {self.probability}")

        if not (0.0 <= self.probability <= 1.0):
            raise ValidationError(f"PredictedTerminal.probability must be in [0, 1], got: {self.probability}")

        if self.latitude is not None:
            self.latitude = float(self.latitude)
            if not (-90.0 <= self.latitude <= 90.0):
                raise ValidationError(f"Latitude out of range [-90, 90]: {self.latitude}")
        if self.longitude is not None:
            self.longitude = float(self.longitude)
            if not (-180.0 <= self.longitude <= 180.0):
                raise ValidationError(f"Longitude out of range [-180, 180]: {self.longitude}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictedTerminal":
        if "terminal_id" not in data or "probability" not in data:
            raise ValidationError("PredictedTerminal requires 'terminal_id' and 'probability'")

        return cls(
            terminal_id=str(data["terminal_id"]),
            probability=float(data["probability"]),
            latitude=float(data["latitude"]) if data.get("latitude") is not None else None,
            longitude=float(data["longitude"]) if data.get("longitude") is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskAlert:
    """Detection output consumed by Alert Dispatcher + Dashboard (schema 6.4, topic 'risk_alerts')."""

    complaint_id: str
    risk_score: float
    flagged_account_id: str
    predicted_terminals: List[PredictedTerminal] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    predicted_window_start: Union[str, datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    predicted_window_end: Union[str, datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    # ADDITIVE (Phase 2): rule-agreement + anomaly-model confidence in [0,1].
    # Optional/None so every existing producer/consumer of RiskAlert keeps
    # working unchanged — see detection/confidence.py.
    confidence: Optional[float] = None

    def __post_init__(self):
        self.complaint_id = str(self.complaint_id)
        try:
            self.risk_score = float(self.risk_score)
        except (ValueError, TypeError):
            raise ValidationError(f"RiskAlert.risk_score must be float, got: {self.risk_score}")

        if not (0.0 <= self.risk_score <= 1.0):
            raise ValidationError(f"RiskAlert.risk_score must be in range [0, 1], got: {self.risk_score}")

        self.flagged_account_id = str(self.flagged_account_id)

        if not isinstance(self.predicted_terminals, list):
            raise ValidationError("RiskAlert.predicted_terminals must be a list")
        if not isinstance(self.evidence, list):
            raise ValidationError("RiskAlert.evidence must be a list")

        # Convert dict terminals to PredictedTerminal objects
        self.predicted_terminals = [
            t if isinstance(t, PredictedTerminal) else PredictedTerminal.from_dict(t)
            for t in self.predicted_terminals
        ]

        if self.confidence is not None:
            self.confidence = max(0.0, min(1.0, float(self.confidence)))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAlert":
        required = [
            "complaint_id",
            "risk_score",
            "flagged_account_id",
            "predicted_terminals",
            "evidence",
            "predicted_window_start",
            "predicted_window_end",
        ]
        for field_name in required:
            if field_name not in data:
                raise ValidationError(f"Missing required field in RiskAlert: '{field_name}'")

        return cls(
            complaint_id=str(data["complaint_id"]),
            risk_score=data["risk_score"],
            flagged_account_id=str(data["flagged_account_id"]),
            predicted_terminals=data["predicted_terminals"],
            evidence=[str(e) for e in data["evidence"]],
            predicted_window_start=data["predicted_window_start"],
            predicted_window_end=data["predicted_window_end"],
            confidence=data.get("confidence"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "complaint_id": self.complaint_id,
            "risk_score": self.risk_score,
            "flagged_account_id": self.flagged_account_id,
            "predicted_terminals": [t.to_dict() if isinstance(t, PredictedTerminal) else t for t in self.predicted_terminals],
            "evidence": list(self.evidence),
            "predicted_window_start": _format_iso(self.predicted_window_start),
            "predicted_window_end": _format_iso(self.predicted_window_end),
            "confidence": self.confidence,
        }


# ============================================================================
# 4. REFERENCE DATA SCHEMAS (Architecture.md §6.2 & §6.3)
# ============================================================================

@dataclass
class AccountNodeMetadata:
    """Static account attributes (schema 6.2); attached at first-seen, not streamed."""

    account_id: str
    account_tier: str = "normal"
    account_age_days: int = 0
    historical_terminal_ids: List[str] = field(default_factory=list)
    district_pincode: Optional[str] = None
    home_district_pincode: Optional[str] = None
    # ADDITIVE (Phase 2): shared KYC identifier (PAN/phone/address hash etc.).
    # Optional, defaults to None so every existing caller/CSV row keeps working
    # unchanged. Powers identity_cluster_rule's "one person, many mule
    # accounts" detection — separate signal from device_fingerprint sharing.
    kyc_identity_id: Optional[str] = None

    def __post_init__(self):
        self.account_id = str(self.account_id)
        self.account_tier = str(self.account_tier)
        try:
            self.account_age_days = int(self.account_age_days)
        except (ValueError, TypeError):
            raise ValidationError(f"account_age_days must be int: {self.account_age_days}")

        if self.account_age_days < 0:
            raise ValidationError(f"account_age_days must be >= 0: {self.account_age_days}")

        if isinstance(self.historical_terminal_ids, str):
            self.historical_terminal_ids = [t.strip() for t in self.historical_terminal_ids.split(",") if t.strip()]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountNodeMetadata":
        return cls(
            account_id=str(data["account_id"]),
            account_tier=str(data.get("account_tier", "normal")),
            account_age_days=int(data.get("account_age_days", 0)),
            historical_terminal_ids=data.get("historical_terminal_ids", []),
            district_pincode=data.get("district_pincode"),
            home_district_pincode=data.get("home_district_pincode") or data.get("district_pincode"),
            kyc_identity_id=data.get("kyc_identity_id") or None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Alias for cross-module compatibility
AccountNode = AccountNodeMetadata


@dataclass
class TerminalNode:
    """Static ATM/AEPS/POS reference row (schema 6.3); loaded once via seed_terminals.py."""

    terminal_id: str
    terminal_type: str = "ATM_KIOSK"
    latitude: float = 0.0
    longitude: float = 0.0
    district_pincode: str = ""
    district: str = ""
    pincode: str = ""
    status: str = "active"

    def __post_init__(self):
        self.terminal_id = str(self.terminal_id)
        self.terminal_type = str(self.terminal_type)
        try:
            self.latitude = float(self.latitude)
            self.longitude = float(self.longitude)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Terminal latitude and longitude must be floats: {e}")

        if not (-90.0 <= self.latitude <= 90.0):
            raise ValidationError(f"Terminal latitude out of range [-90, 90]: {self.latitude}")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValidationError(f"Terminal longitude out of range [-180, 180]: {self.longitude}")

        if not self.district_pincode and self.pincode:
            self.district_pincode = self.pincode
        elif not self.pincode and self.district_pincode:
            self.pincode = self.district_pincode

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerminalNode":
        return cls(
            terminal_id=str(data["terminal_id"]),
            terminal_type=str(data.get("terminal_type", "ATM_KIOSK")),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            district_pincode=str(data.get("district_pincode", data.get("pincode", ""))),
            district=str(data.get("district", "")),
            pincode=str(data.get("pincode", data.get("district_pincode", ""))),
            status=str(data.get("status", "active")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# 5. OPERATIONAL DEMO & INVESTIGATION SCHEMAS (SIH26184 Additions)
# ============================================================================

class CaseLifecycleState:
    """Standardized case lifecycle states for SIH26184."""
    OBSERVED = "OBSERVED"
    SUSPICIOUS = "SUSPICIOUS"
    PREDICTED = "PREDICTED"
    PRE_COMPLAINT_INTERVENTION = "PRE_COMPLAINT_INTERVENTION"
    CASHOUT_ATTEMPT_DETECTED = "CASHOUT_ATTEMPT_DETECTED"
    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"
    POST_COMPLAINT_ESCALATED = "POST_COMPLAINT_ESCALATED"
    POLICE_ALERT_SENT = "POLICE_ALERT_SENT"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RESOLVED = "RESOLVED"


@dataclass
class SelectiveFundProtection:
    """Details of selective fund hold targeting recent suspicious amounts."""

    account_id: str
    existing_balance: float
    suspicious_amount: float
    protected_amount: float
    source_transaction_id: str
    chain_reference: str
    reason: str
    case_id: str = ""
    intervention_type: str = "PROVISIONAL_HOLD"  # PROVISIONAL_HOLD | SELECTIVE_FREEZE | FULL_FREEZE
    status: str = "ACTIVE"                       # ACTIVE | RELEASED | ESCALATED
    timestamp: Union[str, datetime] = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self.account_id = str(self.account_id)
        self.existing_balance = float(self.existing_balance)
        self.suspicious_amount = float(self.suspicious_amount)
        self.protected_amount = float(self.protected_amount)
        self.source_transaction_id = str(self.source_transaction_id)
        self.chain_reference = str(self.chain_reference)
        self.reason = str(self.reason)
        self.case_id = str(self.case_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "account_id": self.account_id,
            "existing_balance": self.existing_balance,
            "suspicious_amount": self.suspicious_amount,
            "protected_amount": self.protected_amount,
            "source_transaction_id": self.source_transaction_id,
            "chain_reference": self.chain_reference,
            "reason": self.reason,
            "intervention_type": self.intervention_type,
            "status": self.status,
            "timestamp": _format_iso(self.timestamp),
        }


@dataclass
class TerminalBlockRequest:
    """Mock request to block cash-out withdrawals at a specific physical terminal."""

    terminal_id: str
    case_id: str
    reason: str = "PREDICTED_CASH_EGRESS"
    action: str = "BLOCK_WITHDRAWAL"
    valid_from: Union[str, datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: Union[str, datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    account_id: Optional[str] = None
    status: str = "REQUESTED"  # REQUESTED | ACTIVE | EXPIRED | LIFTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "terminal_id": self.terminal_id,
            "case_id": self.case_id,
            "reason": self.reason,
            "action": self.action,
            "valid_from": _format_iso(self.valid_from),
            "valid_until": _format_iso(self.valid_until),
            "account_id": self.account_id,
            "status": self.status,
        }


@dataclass
class WithdrawalAttemptEvent:
    """Synthetic cash-out attempt event at a physical ATM / terminal."""

    attempt_id: str
    terminal_id: str
    account_id: str
    amount_inr: float
    timestamp: Union[str, datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    payment_channel: str = "ATM"
    correlated_case_id: Optional[str] = None
    is_blocked: bool = False
    action_taken: str = "MONITORED"  # BLOCKED | FLAGGED | INTERCEPTED | ALLOWED | MONITORED
    status: Optional[str] = None     # ALLOWED | BLOCKED | INTERCEPTED | FLAGGED
    reason: Optional[str] = None
    distance_to_predicted_km: Optional[float] = None
    nearby_terminals: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if self.status is None:
            self.status = "BLOCKED" if self.is_blocked else (self.action_taken if self.action_taken in {"ALLOWED", "BLOCKED", "INTERCEPTED", "FLAGGED"} else "ALLOWED")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "terminal_id": self.terminal_id,
            "account_id": self.account_id,
            "amount_inr": self.amount_inr,
            "timestamp": _format_iso(self.timestamp),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "payment_channel": self.payment_channel,
            "correlated_case_id": self.correlated_case_id,
            "is_blocked": self.is_blocked,
            "action_taken": self.action_taken,
            "status": self.status,
            "reason": self.reason,
            "distance_to_predicted_km": self.distance_to_predicted_km,
            "nearby_terminals": list(self.nearby_terminals),
        }


@dataclass
class LocationEvidenceRecord:
    """Chronological physical ATM / terminal location event associated with an investigation case."""

    case_id: str
    terminal_id: str
    terminal_type: str = "ATM_KIOSK"
    district: str = ""
    district_pincode: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str = "RECORDED_WITHDRAWAL"  # RECORDED_WITHDRAWAL | PREDICTED_EGRESS
    amount_inr: Optional[float] = None
    action_taken: str = "MONITORED"
    status: str = "RECORDED"
    distance_from_predicted_km: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MoneyTrailLeg:
    """Structured hop in a money laundering chain."""

    hop_index: int
    source_account_id: str
    target_account_id: str
    amount_inr: float
    timestamp: str
    payment_channel: str
    direction: str = "in"
    source_tier: str = "victim"
    target_tier: str = "mule"
    suspicious_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TimelineEvent:
    """Chronological event entry in a case's investigation history."""

    event_id: str
    case_id: str
    event_type: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "SYSTEM"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "case_id": self.case_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "source": self.source,
            "details": dict(self.details),
        }


@dataclass
class CaseRecord:
    """Unified investigation case model spanning pre/post complaint lifecycle."""

    case_id: str
    flagged_account_id: str
    state: str = CaseLifecycleState.PRE_COMPLAINT_INTERVENTION
    risk_score: float = 0.0
    confidence: float = 0.0
    band: str = "HIGH"
    priority: str = "HIGH"               # LOW | MEDIUM | HIGH | CRITICAL
    suspicious_amount: float = 0.0
    protected_amount: float = 0.0
    existing_balance: float = 0.0
    money_trail: List[MoneyTrailLeg] = field(default_factory=list)
    predicted_terminals: List[PredictedTerminal] = field(default_factory=list)
    predicted_window_start: str = ""
    predicted_window_end: str = ""
    evidence: List[str] = field(default_factory=list)
    bank_hold_status: str = "NONE"       # NONE | ACTIVE | PROVISIONAL | FULL_FREEZE
    terminal_block_status: str = "NONE"  # NONE | REQUESTED | ACTIVE
    lea_notification_status: str = "NONE"# NONE | SENT | DISPATCHED | ACKNOWLEDGED | UNDER_INVESTIGATION | RESOLVED
    withdrawal_attempts: List[Dict[str, Any]] = field(default_factory=list)
    complaint_id: Optional[str] = None
    fir_number: Optional[str] = None
    escalation_level: int = 1
    police_alert_eligible: bool = False
    police_alert_id: Optional[str] = None
    recovery_case_id: Optional[str] = None
    root_transaction_id: Optional[str] = None
    chain_id: Optional[str] = None
    confirmation_id: Optional[str] = None
    resolution_reason: Optional[str] = None
    resolved_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "flagged_account_id": self.flagged_account_id,
            "state": self.state,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "band": self.band,
            "priority": self.priority,
            "suspicious_amount": self.suspicious_amount,
            "protected_amount": self.protected_amount,
            "existing_balance": self.existing_balance,
            "money_trail": [t.to_dict() if hasattr(t, "to_dict") else t for t in self.money_trail],
            "predicted_terminals": [t.to_dict() if hasattr(t, "to_dict") else t for t in self.predicted_terminals],
            "predicted_window_start": self.predicted_window_start,
            "predicted_window_end": self.predicted_window_end,
            "evidence": list(self.evidence),
            "bank_hold_status": self.bank_hold_status,
            "terminal_block_status": self.terminal_block_status,
            "lea_notification_status": self.lea_notification_status,
            "withdrawal_attempts": list(self.withdrawal_attempts),
            "complaint_id": self.complaint_id,
            "fir_number": self.fir_number,
            "escalation_level": self.escalation_level,
            "police_alert_eligible": self.police_alert_eligible,
            "police_alert_id": self.police_alert_id,
            "recovery_case_id": self.recovery_case_id,
            "root_transaction_id": self.root_transaction_id,
            "chain_id": self.chain_id,
            "confirmation_id": self.confirmation_id,
            "resolution_reason": self.resolution_reason,
            "resolved_at": self.resolved_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# 8. CONFIRMATION & TRANSACTION CONTROL (Part 1 - SIH26184)
# ============================================================================

class ConfirmationStatus:
    """Explicit confirmation states for marked / unusual transfers."""

    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED_LEGITIMATE = "CONFIRMED_LEGITIMATE"
    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"
    NO_RESPONSE = "NO_RESPONSE"
    EXPIRED = "EXPIRED"


class TransactionChannel:
    """Standard categorized transaction channels."""

    ONLINE_TRANSFER = "ONLINE_TRANSFER"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"

    @classmethod
    def classify(cls, channel_name: str) -> str:
        """Classify specific payment channel string into standard channel category."""
        clean = str(channel_name).upper().strip()
        if clean in {"ATM", "ATM_CASH_OUT", "AEPS_CASH_OUT", "CASH_WITHDRAWAL", "MICRO_ATM", "POS_CASH", "BRANCH_CASH"}:
            return cls.CASH_WITHDRAWAL
        return cls.ONLINE_TRANSFER


class ControlAction:
    """Transaction control policy decisions."""

    ALLOW = "ALLOW"
    MONITOR = "MONITOR"
    RESTRICT = "RESTRICT"
    FREEZE = "FREEZE"


@dataclass
class TransactionControlDecision:
    """Actionable decision returned by the transaction control engine."""

    transaction_id: str
    account_id: str
    channel: str
    amount_inr: float
    action: str  # ALLOW | MONITOR | RESTRICT | FREEZE
    allowed: bool
    reason: str
    held_amount: float = 0.0
    available_balance: float = 0.0
    correlated_case_id: Optional[str] = None
    confirmation_id: Optional[str] = None
    timestamp: Union[str, datetime] = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "account_id": self.account_id,
            "channel": self.channel,
            "amount_inr": self.amount_inr,
            "action": self.action,
            "allowed": self.allowed,
            "reason": self.reason,
            "held_amount": self.held_amount,
            "available_balance": self.available_balance,
            "correlated_case_id": self.correlated_case_id,
            "confirmation_id": self.confirmation_id,
            "timestamp": _format_iso(self.timestamp),
        }


@dataclass
class ConfirmationRecord:
    """Customer confirmation lifecycle record for unusual/high-value transactions."""

    confirmation_id: str
    transaction_id: str
    originating_account_id: str
    destination_account_id: str
    amount_inr: float
    status: str = ConfirmationStatus.PENDING_CONFIRMATION
    requested_at: Union[str, datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    responded_at: Optional[Union[str, datetime]] = None
    expires_at: Optional[Union[str, datetime]] = None
    outcome: Optional[str] = None
    case_id: Optional[str] = None
    intervention_state: str = "PROVISIONAL_MONITORING"
    downstream_transaction_ids: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confirmation_id": self.confirmation_id,
            "transaction_id": self.transaction_id,
            "originating_account_id": self.originating_account_id,
            "destination_account_id": self.destination_account_id,
            "amount_inr": self.amount_inr,
            "status": self.status,
            "requested_at": _format_iso(self.requested_at),
            "responded_at": _format_iso(self.responded_at) if self.responded_at else None,
            "expires_at": _format_iso(self.expires_at) if self.expires_at else None,
            "outcome": self.outcome,
            "case_id": self.case_id,
            "intervention_state": self.intervention_state,
            "downstream_transaction_ids": list(self.downstream_transaction_ids),
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class RecoveryWorkflowRecord:
    """Actionable recovery and fund recall workflow generated upon confirmed fraud."""

    workflow_id: str
    case_id: str
    originating_transaction_id: str
    fraud_amount: float
    recovered_or_held_amount: float
    affected_accounts: List[str] = field(default_factory=list)
    action_items: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "INITIATED"  # INITIATED | IN_PROGRESS | COMPLETED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "case_id": self.case_id,
            "originating_transaction_id": self.originating_transaction_id,
            "fraud_amount": self.fraud_amount,
            "recovered_or_held_amount": self.recovered_or_held_amount,
            "affected_accounts": list(self.affected_accounts),
            "action_items": list(self.action_items),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# 9. FUND TRACEABILITY & RECOVERY (Part 2 - SIH26184)
# ============================================================================

class RecoveryState:
    """Explicit lifecycle states for fraud recovery workflows."""

    NOT_STARTED = "NOT_STARTED"
    TRACING = "TRACING"
    INTERVENTION_PENDING = "INTERVENTION_PENDING"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    PARTIALLY_RECOVERED = "PARTIALLY_RECOVERED"
    RECOVERED = "RECOVERED"
    UNRECOVERABLE = "UNRECOVERABLE"


@dataclass
class AccountExposureRecord:
    """Maintains traceable suspicious exposure alongside legitimate balances for commingled accounts."""

    account_id: str
    legitimate_balance: float = 0.0
    suspicious_exposure: float = 0.0
    total_balance: float = 0.0
    contributing_root_transactions: List[str] = field(default_factory=list)
    active_chains: List[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if self.total_balance == 0.0 and (self.legitimate_balance > 0 or self.suspicious_exposure > 0):
            self.total_balance = self.legitimate_balance + self.suspicious_exposure

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "legitimate_balance": self.legitimate_balance,
            "suspicious_exposure": self.suspicious_exposure,
            "total_balance": self.total_balance,
            "contributing_root_transactions": list(self.contributing_root_transactions),
            "active_chains": list(self.active_chains),
            "last_updated": self.last_updated,
        }


@dataclass
class TransactionChainEdge:
    """A single directed leg in a downstream fund provenance chain."""

    chain_id: str
    parent_transaction_id: Optional[str]
    child_transaction_id: str
    from_account_id: str
    to_account_id: str
    amount_inr: float
    payment_channel: str
    timestamp: str
    hop_depth: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransactionChainRecord:
    """Complete downstream money trail and provenance metadata rooted at an originating transaction."""

    chain_id: str
    root_transaction_id: str
    origin_account_id: str
    destination_account_chain: List[str] = field(default_factory=list)
    original_amount: float = 0.0
    traceable_transactions: List[Dict[str, Any]] = field(default_factory=list)
    current_known_accounts: List[str] = field(default_factory=list)
    known_withdrawals: List[Dict[str, Any]] = field(default_factory=list)
    traceable_exposed_amounts: Dict[str, float] = field(default_factory=dict)
    chain_depth: int = 1
    chain_status: str = "ACTIVE"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "root_transaction_id": self.root_transaction_id,
            "origin_account_id": self.origin_account_id,
            "destination_account_chain": list(self.destination_account_chain),
            "original_amount": self.original_amount,
            "traceable_transactions": list(self.traceable_transactions),
            "current_known_accounts": list(self.current_known_accounts),
            "known_withdrawals": list(self.known_withdrawals),
            "traceable_exposed_amounts": dict(self.traceable_exposed_amounts),
            "chain_depth": self.chain_depth,
            "chain_status": self.chain_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class RecoveryCaseRecord:
    """Formal investigation recovery case tracking funds across the entire downstream money trail."""

    case_id: str
    root_transaction_id: str
    chain_id: str
    origin_account: str
    destination_account_chain: List[str] = field(default_factory=list)
    original_amount: float = 0.0
    traceable_transactions: List[Dict[str, Any]] = field(default_factory=list)
    current_known_accounts: List[str] = field(default_factory=list)
    known_withdrawals: List[Dict[str, Any]] = field(default_factory=list)
    traceable_exposed_amounts: Dict[str, float] = field(default_factory=dict)
    recovery_status: str = RecoveryState.NOT_STARTED
    recovered_amount: float = 0.0
    simulated_actions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "root_transaction_id": self.root_transaction_id,
            "chain_id": self.chain_id,
            "origin_account": self.origin_account,
            "destination_account_chain": list(self.destination_account_chain),
            "original_amount": self.original_amount,
            "traceable_transactions": list(self.traceable_transactions),
            "current_known_accounts": list(self.current_known_accounts),
            "known_withdrawals": list(self.known_withdrawals),
            "traceable_exposed_amounts": dict(self.traceable_exposed_amounts),
            "recovery_status": self.recovery_status,
            "recovered_amount": self.recovered_amount,
            "simulated_actions": list(self.simulated_actions),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ConvergentChainsRecord:
    """Aggregates multiple victim transactions converging into a common aggregator or mule account."""

    common_account_id: str
    source_transactions: List[Dict[str, Any]] = field(default_factory=list)
    root_transaction_ids: List[str] = field(default_factory=list)
    chain_ids: List[str] = field(default_factory=list)
    aggregate_suspicious_exposure: float = 0.0
    downstream_chain: List[Dict[str, Any]] = field(default_factory=list)
    related_case_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "common_account_id": self.common_account_id,
            "source_transactions": list(self.source_transactions),
            "root_transaction_ids": list(self.root_transaction_ids),
            "chain_ids": list(self.chain_ids),
            "aggregate_suspicious_exposure": self.aggregate_suspicious_exposure,
            "downstream_chain": list(self.downstream_chain),
            "related_case_ids": list(self.related_case_ids),
        }


# ============================================================================
# 10. POLICE ALERT & DELIVERY SCHEMAS (Part 5 - SIH26184)
# ============================================================================

class PoliceAlertStatus:
    """Standardized lifecycle states for police alerts."""

    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


@dataclass
class PoliceAlertRecord:
    """Structured police alert payload generated upon explicit bank official escalation."""

    police_alert_id: str
    case_id: str
    alert_status: str = PoliceAlertStatus.SENT
    priority: str = "HIGH"
    source: str = "CyberShield Bank Official"
    incident: Dict[str, Any] = field(default_factory=dict)
    origin_transaction: Dict[str, Any] = field(default_factory=dict)
    money_trail: List[Dict[str, Any]] = field(default_factory=list)
    relevant_accounts: List[str] = field(default_factory=list)
    withdrawal_attempts: List[Dict[str, Any]] = field(default_factory=list)
    nearby_terminals: List[Dict[str, Any]] = field(default_factory=list)
    location_timeline: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "police_alert_id": self.police_alert_id,
            "case_id": self.case_id,
            "alert_status": self.alert_status,
            "priority": self.priority,
            "source": self.source,
            "incident": dict(self.incident),
            "origin_transaction": dict(self.origin_transaction),
            "money_trail": list(self.money_trail),
            "relevant_accounts": list(self.relevant_accounts),
            "withdrawal_attempts": list(self.withdrawal_attempts),
            "nearby_terminals": list(self.nearby_terminals),
            "location_timeline": list(self.location_timeline),
            "evidence": list(self.evidence),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by,
            "notes": self.notes,
        }


# ============================================================================
# 11. NOTIFICATION SYSTEM SCHEMAS (Sprint 4 - SIH26184)
# ============================================================================

class NotificationChannel:
    """Supported delivery channels."""
    SMS = "SMS"
    EMAIL = "EMAIL"


class NotificationEventType:
    """Operational events that trigger notification dispatch."""
    HIGH_RISK_CASE = "HIGH_RISK_CASE"
    CONFIRMED_FRAUD = "CONFIRMED_FRAUD"
    CASHOUT_ATTEMPT_DETECTED = "CASHOUT_ATTEMPT_DETECTED"
    WITHDRAWAL_BLOCKED = "WITHDRAWAL_BLOCKED"
    CASE_ESCALATED = "CASE_ESCALATED"
    POLICE_ALERT_SENT = "POLICE_ALERT_SENT"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"


class NotificationDeliveryStatus:
    """Lifecycle states of a notification delivery attempt."""
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class NotificationRecipientGroup:
    """Configurable recipient groups."""
    BANK_OFFICIAL = "BANK_OFFICIAL"
    SECURITY_TEAM = "SECURITY_TEAM"
    INVESTIGATION_TEAM = "INVESTIGATION_TEAM"


@dataclass
class NotificationRecord:
    """Persisted record of an SMS or Email notification attempt."""
    notification_id: str
    case_id: str
    event_type: str
    channel: str
    recipient: str
    recipient_group: str = NotificationRecipientGroup.BANK_OFFICIAL
    subject: str = ""
    message_body: str = ""
    status: str = NotificationDeliveryStatus.PENDING
    is_simulated: bool = True
    retry_count: int = 0
    error: Optional[str] = None
    idempotency_key: Optional[str] = None
    payload_json: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sent_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "case_id": self.case_id,
            "event_type": self.event_type,
            "channel": self.channel,
            "recipient": self.recipient,
            "recipient_group": self.recipient_group,
            "subject": self.subject,
            "message_body": self.message_body,
            "status": self.status,
            "is_simulated": bool(self.is_simulated),
            "retry_count": self.retry_count,
            "error": self.error,
            "idempotency_key": self.idempotency_key,
            "payload_json": dict(self.payload_json),
            "created_at": self.created_at,
            "sent_at": self.sent_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationRecord":
        payload = data.get("payload_json")
        if isinstance(payload, str):
            try:
                import json
                payload = json.loads(payload)
            except Exception:
                payload = {}
        elif not isinstance(payload, dict):
            payload = {}

        return cls(
            notification_id=str(data["notification_id"]),
            case_id=str(data["case_id"]),
            event_type=str(data.get("event_type", "")),
            channel=str(data.get("channel", "")),
            recipient=str(data.get("recipient", "")),
            recipient_group=str(data.get("recipient_group", NotificationRecipientGroup.BANK_OFFICIAL)),
            subject=str(data.get("subject", "")),
            message_body=str(data.get("message_body", "")),
            status=str(data.get("status", NotificationDeliveryStatus.PENDING)),
            is_simulated=bool(data.get("is_simulated", True)),
            retry_count=int(data.get("retry_count", 0)),
            error=data.get("error"),
            idempotency_key=data.get("idempotency_key"),
            payload_json=payload,
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
            sent_at=data.get("sent_at"),
        )


@dataclass
class NotificationRequest:
    """Request payload sent to NotificationProvider adapters."""
    case_id: str
    event_type: str
    channel: str
    recipient: str
    recipient_group: str = NotificationRecipientGroup.BANK_OFFICIAL
    subject: str = ""
    message_body: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
