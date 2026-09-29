"""tests/test_leakage_guard.py — Temporal cutoff leakage guard tests."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from detection.terminal_ranking import rank_terminals
from pipeline.graph_store import GraphStore, utcnow
from shared.schemas import AccountNodeMetadata, TerminalNode, TransactionEvent


def test_leakage_guard_temporal_cutoff():
    """Verify that rank_terminals with as_of=T ignores transactions/activity after T."""
    g = GraphStore()
    t1 = TerminalNode(terminal_id="ATM-001", latitude=28.60, longitude=77.20, district_pincode="110001")
    t2 = TerminalNode(terminal_id="ATM-002", latitude=28.70, longitude=77.30, district_pincode="110002")
    g.load_terminals([t1.to_dict(), t2.to_dict()])

    g.add_account_metadata(AccountNodeMetadata(account_id="ACC-TEST", district_pincode="110001"))

    # Cutoff time T
    t_cutoff = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Valid transaction BEFORE cutoff
    g.add_transaction(TransactionEvent(
        transaction_id="TXN-BEFORE",
        source_account_id="ACC-BEFORE",
        target_account_id="ACC-TEST",
        amount_inr=10000.0,
        timestamp="2026-09-01T11:00:00Z",
        payment_channel="UPI",
        device_fingerprint="DEV-001"
    ))

    # Post-cutoff transaction AFTER T (future event)
    g.add_transaction(TransactionEvent(
        transaction_id="TXN-AFTER",
        source_account_id="ACC-TEST",
        target_account_id="ACC-FUTURE-MULE",
        amount_inr=50000.0,
        timestamp="2026-09-01T13:00:00Z",
        payment_channel="UPI",
        device_fingerprint="DEV-002"
    ))

    # Record post-cutoff terminal usage
    g.record_account_terminal_activity("ACC-FUTURE-MULE", "ATM-002", timestamp=datetime(2026, 9, 1, 13, 30, 0, tzinfo=timezone.utc))

    # Ranking WITHOUT as_of includes post-cutoff node ACC-FUTURE-MULE in neighborhood
    nbrs_no_cutoff = g.get_neighborhood("ACC-TEST", degrees=1, as_of=None)
    assert "ACC-FUTURE-MULE" in nbrs_no_cutoff

    # Ranking WITH as_of=t_cutoff strictly excludes post-cutoff node
    nbrs_cutoff = g.get_neighborhood("ACC-TEST", degrees=1, as_of=t_cutoff)
    assert "ACC-FUTURE-MULE" not in nbrs_cutoff

    # Ensure rank_terminals respects as_of cutoff
    scores_cutoff = rank_terminals(g, "ACC-TEST", [t1, t2], as_of=t_cutoff)
    assert len(scores_cutoff) == 2
    # Verify ATM-002 historical affinity from future mule is NOT leaked
    assert scores_cutoff[0].terminal.terminal_id == "ATM-001"


def test_leakage_guard_fails_when_future_data_injected():
    """Verify that injecting a future ground-truth terminal changes predictions if as_of is NOT enforced."""
    g = GraphStore()
    t1 = TerminalNode(terminal_id="ATM-001", latitude=28.60, longitude=77.20, district_pincode="110001")
    t2 = TerminalNode(terminal_id="ATM-002", latitude=28.70, longitude=77.30, district_pincode="110002")
    g.load_terminals([t1.to_dict(), t2.to_dict()])

    g.add_account_metadata(AccountNodeMetadata(account_id="ACC-MULE", district_pincode="110001", historical_terminal_ids=["ATM-001"]))

    t_cutoff = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Initial state before cutoff
    g.add_transaction(TransactionEvent(
        transaction_id="TXN-1",
        source_account_id="ACC-SRC",
        target_account_id="ACC-MULE",
        amount_inr=15000.0,
        timestamp="2026-09-01T10:00:00Z",
        payment_channel="UPI",
        device_fingerprint="DEV-001"
    ))

    # Score at cutoff T (ATM-001 ranked top)
    rank_with_cutoff = rank_terminals(g, "ACC-MULE", [t1, t2], as_of=t_cutoff)

    # Inject post-cutoff terminal activity at T + 2 hours
    g._terminal_usage["ACC-MULE"].append({
        "terminal_id": "ATM-002",
        "timestamp": "2026-09-01T14:00:00Z"
    })

    # Ranking WITH as_of=t_cutoff ignores the future terminal usage
    rank_protected = rank_terminals(g, "ACC-MULE", [t1, t2], as_of=t_cutoff)
    assert rank_protected[0].terminal.terminal_id == "ATM-001"
    assert rank_protected[0].priority == rank_with_cutoff[0].priority
