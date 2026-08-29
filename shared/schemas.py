"""
shared/schemas.py

Locked schema contract definitions matching Architecture.md §6 and the
intermediate pipeline contract agreed across workstreams.

These schemas provide strongly typed dataclasses and runtime validation for:
1. TransactionEvent (topic: "transactions")
2. GraphSignal (topic: "graph_signals")
3. RiskAlert (topic: "risk_alerts")
4. AccountNode & TerminalNode (reference data)
"""

from dataclasses import dataclass, field, asdict
from typing import Any


class ValidationError(ValueError):
    """Raised when a dictionary payload fails schema validation."""
    pass


# ============================================================================
# 1. TRANSACTION EVENT (Architecture.md §6.1)
# ============================================================================

@dataclass
class TransactionEvent:
    transaction_id: str
    source_account_id: str
    target_account_id: str
    amount_inr: float
    timestamp: str
    payment_channel: str
    device_fingerprint: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransactionEvent":
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

        try:
            amount = float(data["amount_inr"])
        except (ValueError, TypeError):
            raise ValidationError(f"TransactionEvent.amount_inr must be float, got: {type(data.get('amount_inr'))}")

        return cls(
            transaction_id=str(data["transaction_id"]),
            source_account_id=str(data["source_account_id"]),
            target_account_id=str(data["target_account_id"]),
            amount_inr=amount,
            timestamp=str(data["timestamp"]),
            payment_channel=str(data["payment_channel"]),
            device_fingerprint=str(data["device_fingerprint"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# 2. GRAPH SIGNAL (Pipeline Intermediate Topic Contract)
# ============================================================================

@dataclass
class GraphSignal:
    account_id: str
    timestamp: str
    fan_in_count: int
    fan_out_count: int
    distinct_counterparties: int
    shared_device_accounts: list[str] = field(default_factory=list)
    chain_depth: int = 0
    historical_terminal_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GraphSignal":
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
            raise ValidationError("GraphSignal.shared_device_accounts must be a list")

        if not isinstance(data.get("historical_terminal_ids"), list):
            raise ValidationError("GraphSignal.historical_terminal_ids must be a list")

        try:
            fan_in = int(data["fan_in_count"])
            fan_out = int(data["fan_out_count"])
            distinct_cp = int(data["distinct_counterparties"])
            chain_depth = int(data["chain_depth"])
        except (ValueError, TypeError) as e:
            raise ValidationError(f"GraphSignal numeric fields must be integers: {e}")

        return cls(
            account_id=str(data["account_id"]),
            timestamp=str(data["timestamp"]),
            fan_in_count=fan_in,
            fan_out_count=fan_out,
            distinct_counterparties=distinct_cp,
            shared_device_accounts=[str(x) for x in data["shared_device_accounts"]],
            chain_depth=chain_depth,
            historical_terminal_ids=[str(x) for x in data["historical_terminal_ids"]],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# 3. RISK ALERT (Architecture.md §6.4)
# ============================================================================

@dataclass
class PredictedTerminal:
    terminal_id: str
    probability: float
    latitude: float | None = None
    longitude: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PredictedTerminal":
        if "terminal_id" not in data or "probability" not in data:
            raise ValidationError("PredictedTerminal requires 'terminal_id' and 'probability'")

        try:
            prob = float(data["probability"])
            lat = float(data["latitude"]) if data.get("latitude") is not None else None
            lon = float(data["longitude"]) if data.get("longitude") is not None else None
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid numeric value in PredictedTerminal: {e}")

        return cls(
            terminal_id=str(data["terminal_id"]),
            probability=prob,
            latitude=lat,
            longitude=lon,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskAlert:
    complaint_id: str
    risk_score: float
    flagged_account_id: str
    predicted_terminals: list[PredictedTerminal]
    evidence: list[str]
    predicted_window_start: str
    predicted_window_end: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskAlert":
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

        if not isinstance(data.get("predicted_terminals"), list):
            raise ValidationError("RiskAlert.predicted_terminals must be a list")

        if not isinstance(data.get("evidence"), list):
            raise ValidationError("RiskAlert.evidence must be a list")

        try:
            score = float(data["risk_score"])
        except (ValueError, TypeError):
            raise ValidationError(f"RiskAlert.risk_score must be float, got: {type(data.get('risk_score'))}")

        terminals = [
            t if isinstance(t, PredictedTerminal) else PredictedTerminal.from_dict(t)
            for t in data["predicted_terminals"]
        ]

        return cls(
            complaint_id=str(data["complaint_id"]),
            risk_score=score,
            flagged_account_id=str(data["flagged_account_id"]),
            predicted_terminals=terminals,
            evidence=[str(e) for e in data["evidence"]],
            predicted_window_start=str(data["predicted_window_start"]),
            predicted_window_end=str(data["predicted_window_end"]),
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["predicted_terminals"] = [t.to_dict() if isinstance(t, PredictedTerminal) else t for t in self.predicted_terminals]
        return d


# ============================================================================
# 4. REFERENCE DATA SCHEMAS (Architecture.md §6.2 & §6.3)
# ============================================================================

@dataclass
class AccountNode:
    account_id: str
    account_age_days: int
    historical_terminal_ids: list[str]
    home_district_pincode: str
    account_tier: str = "normal"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AccountNode":
        terminals = data.get("historical_terminal_ids", [])
        if isinstance(terminals, str):
            terminals = [t.strip() for t in terminals.split(",") if t.strip()]
        return cls(
            account_id=str(data["account_id"]),
            account_age_days=int(data.get("account_age_days", 0)),
            historical_terminal_ids=terminals,
            home_district_pincode=str(data.get("home_district_pincode", "")),
            account_tier=str(data.get("account_tier", "normal")),
        )


@dataclass
class TerminalNode:
    terminal_id: str
    terminal_type: str
    latitude: float
    longitude: float
    district: str
    pincode: str
    status: str = "active"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TerminalNode":
        return cls(
            terminal_id=str(data["terminal_id"]),
            terminal_type=str(data.get("terminal_type", "ATM")),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            district=str(data.get("district", "")),
            pincode=str(data.get("pincode", "")),
            status=str(data.get("status", "active")),
        )
