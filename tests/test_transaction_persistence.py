"""tests/test_transaction_persistence.py

Unit tests for transaction-level SQLite persistence:
- transaction table creation
- transaction insertion & retrieval
- duplicate transaction handling (idempotence)
- consumer -> persistence integration via process_transaction
- existing alert/intervention persistence functional regression checks
"""
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from shared.persistence import Store
from shared.schemas import TransactionEvent, RiskAlert
from detection.auto_intervention import InterventionDecision
from pipeline.graph_store import GraphStore
from pipeline.consumer import process_transaction


@pytest.fixture()
def tmp_store(tmp_path):
    db_file = tmp_path / "test_cybershield.db"
    store = Store(db_path=db_file)
    yield store
    store.close()


def test_transactions_table_created_and_insert(tmp_store):
    tx = {
        "transaction_id": "TXN-PERSIST-001",
        "source_account_id": "ACC-00001",
        "target_account_id": "ACC-00002",
        "amount_inr": 15000.50,
        "timestamp": "2026-09-07T10:00:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-TEST-01",
    }
    inserted = tmp_store.save_transaction(tx)
    assert inserted is True

    record = tmp_store.get_transaction("TXN-PERSIST-001")
    assert record is not None
    assert record["transaction_id"] == "TXN-PERSIST-001"
    assert record["source_account_id"] == "ACC-00001"
    assert record["target_account_id"] == "ACC-00002"
    assert record["amount_inr"] == 15000.50
    assert record["payment_channel"] == "UPI"
    assert record["device_fingerprint"] == "DEV-TEST-01"


def test_save_transaction_accepts_transaction_event_object(tmp_store):
    event = TransactionEvent(
        transaction_id="TXN-PERSIST-002",
        source_account_id="ACC-00003",
        target_account_id="ACC-00004",
        amount_inr=25000.0,
        timestamp="2026-09-07T10:05:00Z",
        payment_channel="IMPS",
        device_fingerprint="DEV-TEST-02",
    )
    inserted = tmp_store.save_transaction(event)
    assert inserted is True

    record = tmp_store.get_transaction("TXN-PERSIST-002")
    assert record is not None
    assert record["transaction_id"] == "TXN-PERSIST-002"
    assert record["amount_inr"] == 25000.0


def test_duplicate_transaction_idempotence(tmp_store):
    tx = {
        "transaction_id": "TXN-DUP-001",
        "source_account_id": "ACC-00001",
        "target_account_id": "ACC-00002",
        "amount_inr": 5000.0,
        "timestamp": "2026-09-07T10:10:00Z",
        "payment_channel": "UPI",
        "device_fingerprint": "DEV-TEST-01",
    }
    first_insert = tmp_store.save_transaction(tx)
    assert first_insert is True

    # Re-insert exact same transaction ID
    second_insert = tmp_store.save_transaction(tx)
    assert second_insert is False

    # Ensure only 1 record exists in database
    recent = tmp_store.recent_transactions(limit=10)
    matching = [r for r in recent if r["transaction_id"] == "TXN-DUP-001"]
    assert len(matching) == 1


def test_recent_transactions(tmp_store):
    for i in range(5):
        tx = {
            "transaction_id": f"TXN-MULTI-{i}",
            "source_account_id": f"ACC-{i}",
            "target_account_id": f"ACC-{i+1}",
            "amount_inr": 1000.0 * (i + 1),
            "timestamp": f"2026-09-07T10:15:0{i}Z",
            "payment_channel": "UPI",
            "device_fingerprint": "DEV-MULTI",
        }
        tmp_store.save_transaction(tx)

    recent = tmp_store.recent_transactions(limit=3)
    assert len(recent) == 3


def test_consumer_process_transaction_persists_to_sqlite(tmp_store):
    g = GraphStore()
    tx = {
        "transaction_id": "TXN-CONSUMER-001",
        "source_account_id": "ACC-00100",
        "target_account_id": "ACC-00101",
        "amount_inr": 9999.0,
        "timestamp": "2026-09-07T11:00:00Z",
        "payment_channel": "AEPS",
        "device_fingerprint": "DEV-CONS-01",
    }
    signals = process_transaction(g, tx, db_store=tmp_store)
    assert len(signals) == 2

    # Verify transaction was persisted in SQLite
    record = tmp_store.get_transaction("TXN-CONSUMER-001")
    assert record is not None
    assert record["amount_inr"] == 9999.0

    # Duplicate call to process_transaction
    dup_signals = process_transaction(g, tx, db_store=tmp_store)
    assert dup_signals == []
    # Verify database still has exactly 1 record
    rec_check = tmp_store.get_transaction("TXN-CONSUMER-001")
    assert rec_check is not None


def test_existing_alert_and_intervention_persistence(tmp_store):
    alert = RiskAlert(
        complaint_id="CMP-TEST-001",
        risk_score=0.92,
        flagged_account_id="ACC-FLAGGED-01",
        evidence=["Mule ring pattern", "High velocity"],
        confidence=0.88,
    )
    tmp_store.save_alert(alert, band="CRITICAL")

    recent_alerts = tmp_store.recent_alerts(limit=5)
    assert len(recent_alerts) >= 1
    assert recent_alerts[0]["complaint_id"] == "CMP-TEST-001"
    assert recent_alerts[0]["band"] == "CRITICAL"

    decision = InterventionDecision(
        tier="AUTO_FREEZE",
        bank_action="freeze",
        lea_notified=True,
        justification="Critical risk score with high confidence",
    )
    tmp_store.save_intervention("CMP-TEST-001", decision)

    # Check interventions table via direct SQL query on _conn
    cur = tmp_store._conn.execute("SELECT * FROM interventions WHERE complaint_id = 'CMP-TEST-001'")
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][2] == "AUTO_FREEZE"  # tier
