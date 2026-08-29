"""The 4 JSON schemas from Architecture.md section 6 — the shared contract.

All 3 workstreams import this one file; do not redefine these locally.
Changes to any field MUST be posted in the group chat BEFORE building against them.

Modeled with pydantic (Rules.md section 3) so schema mismatches throw early.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


def _parse_iso_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC (assume UTC if naive)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value.astimezone(datetime.now().astimezone().tzinfo)


class TransactionEvent(BaseModel):
    """One payment leg between two accounts (schema 6.1, topic 'transactions')."""

    transaction_id: str
    source_account_id: str = Field(..., regex=r"^ACC-[A-Za-z0-9]+$")
    target_account_id: str = Field(..., regex=r"^ACC-[A-Za-z0-9]+$")
    amount_inr: float = Field(..., gt=0)
    timestamp: datetime
    payment_channel: str = Field(
        ..., regex=r"^(UPI|IMPS|NEFT|RTGS|AEPS)$"
    )
    device_fingerprint: str

    @property
    def timestamp_utc(self) -> datetime:
        """UTC-normalized timestamp used by the graph/rules."""
        return _parse_iso_utc(self.timestamp)


class AccountNodeMetadata(BaseModel):
    """Static account attributes (schema 6.2); attached at first-seen, not streamed."""

    account_id: str
    account_tier: str = Field(..., regex=r"^(victim|mule_l1|mule_l2|aggregator|[a-z_]+)$")
    account_age_days: int = Field(..., ge=0)
    historical_terminal_ids: List[str] = Field(default_factory=list)
    district_pincode: Optional[str] = None


class TerminalNode(BaseModel):
    """Static ATM/AEPS/POS reference row (schema 6.3); loaded once via seed_terminals.py."""

    terminal_id: str
    terminal_type: str = Field(..., regex=r"^(ATM_KIOSK|AEPS_MICRO_ATM|POS)$")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    district_pincode: str


class PredictedTerminal(BaseModel):
    """One ranked cash-out candidate inside a RiskAlert (schema 6.4)."""

    terminal_id: str
    probability: float = Field(..., ge=0, le=1)  # priority score, NOT a calibrated probability
    latitude: float
    longitude: float


class RiskAlert(BaseModel):
    """Detection output consumed by Alert Dispatcher + Dashboard (schema 6.4, topic 'risk_alerts')."""

    complaint_id: str
    risk_score: float = Field(..., ge=0, le=1)
    flagged_account_id: str
    predicted_terminals: List[PredictedTerminal] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    predicted_window_start: datetime
    predicted_window_end: datetime