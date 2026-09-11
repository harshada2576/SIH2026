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
