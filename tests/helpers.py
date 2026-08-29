"""Test helpers: build tiny FraudStore graphs from realistic event/metadata pairs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

from pipeline.graph_store import GraphStore
from shared.schemas import AccountNodeMetadata, TransactionEvent


def _aid(value: str) -> str:
    """Ensure an account id carries the mandatory ACC- prefix (schema 6.1)."""
    return value if value.startswith("ACC-") else f"ACC-{value}"


def aid(value: str) -> str:
    """Public alias — use this to look up a built account in a rule/evaluate call."""
    return _aid(value)


def now_utc() -> datetime:
    """Fixed-ish reference time: short-duration tests all sit inside the 1h window."""
    return datetime.now(timezone.utc)


def txn(
    tid: str,
    src: str,
    tgt: str,
    amount: float,
    when: datetime,
    channel: str = "UPI",
    device: str = "DEV-0",
) -> TransactionEvent:
    """Build one TransactionEvent with all required fields."""
    return TransactionEvent(
        transaction_id=tid, source_account_id=_aid(src), target_account_id=_aid(tgt),
        amount_inr=amount, timestamp=when, payment_channel=channel,
        device_fingerprint=device)


def acct(
    account_id: str,
    tier: str = "aggregator",
    age: int = 500,
    terminals: Optional[Iterable[str]] = None,
    pincode: Optional[str] = None,
) -> AccountNodeMetadata:
    """Build one AccountNodeMetadata row; defaults to a boring old account."""
    return AccountNodeMetadata(
        account_id=_aid(account_id), account_tier=tier, account_age_days=age,
        historical_terminal_ids=list(terminals or []), district_pincode=pincode)


def graph_with(
    events: Iterable[TransactionEvent],
    metas: Optional[Iterable[AccountNodeMetadata]] = None,
) -> GraphStore:
    """Fresh graph populated with the given events + metadata."""
    g = GraphStore()
    for e in events:
        g.add_transaction(e)
    for m in metas or []:
        g.add_account_metadata(m)
    return g


def minutes_ago(n: int, base: Optional[datetime] = None) -> datetime:
    """`n` minutes before `base` (defaults to now_utc()) for windowed tests."""
    base = base or now_utc()
    return base - timedelta(minutes=n)