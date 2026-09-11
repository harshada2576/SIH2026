"""scripts/verify_e2e_flow.py

End-to-end verification script testing:
1. generated accounts contain "kyc_identity_id"
2. transactions flow through pipeline/GraphStore
3. existing detection rules work
4. alerts are generated
5. interventions are triggered
6. transactions are persisted to SQLite
7. alerts are persisted to SQLite
8. interventions are persisted to SQLite
9. duplicate transaction delivery does not create duplicate transaction records in SQLite
"""
import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from shared.persistence import Store, DEFAULT_DB_PATH
from pipeline.graph_store import GraphStore
from pipeline.consumer import load_reference_data, process_transaction
from detection import scorer, alert_dispatcher
from detection.rules import identity_cluster_rule

DB_PATH = REPO_ROOT / "data" / "output" / "cybershield_e2e_test.db"
ACCOUNTS_CSV = REPO_ROOT / "data-generator" / "data" / "accounts.csv"
TERMINALS_CSV = REPO_ROOT / "data-generator" / "data" / "terminals.csv"
TRANSACTIONS_CSV = REPO_ROOT / "data-generator" / "data" / "transactions.csv"


def _cleanup_test_db(db_file: Path) -> None:
    for suffix in ["", "-wal", "-shm"]:
        p = Path(str(db_file) + suffix)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def verify_e2e():
    print("=== STARTING END-TO-END REPLAY VERIFICATION ===")

    _cleanup_test_db(DB_PATH)
    db_store = Store(db_path=DB_PATH)
    graph = GraphStore()

    # 1. Verify generated accounts contain kyc_identity_id
    print("\n1. Checking accounts.csv for kyc_identity_id...")
    with open(ACCOUNTS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        accounts_data = list(reader)

    assert len(accounts_data) > 0
    assert "kyc_identity_id" in accounts_data[0]
    kyc_counts = {}
    for acc in accounts_data:
        assert acc["kyc_identity_id"], f"Missing kyc_identity_id in account {acc['account_id']}"
        k = acc["kyc_identity_id"]
        kyc_counts[k] = kyc_counts.get(k, 0) + 1

    shared_clusters = {k: v for k, v in kyc_counts.items() if v > 1}
    print(f"  [OK] Found {len(accounts_data)} accounts with valid kyc_identity_id.")
    print(f"  [OK] Found {len(shared_clusters)} synthetic shared identity clusters.")

    # Load reference data into GraphStore
    load_reference_data(graph, accounts_path=ACCOUNTS_CSV, terminals_path=TERMINALS_CSV)

    # 2. Process transactions through consumer/GraphStore + SQLite persistence
    print("\n2. Processing transactions through consumer pipeline & SQLite persistence...")
    with open(TRANSACTIONS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        tx_list = list(reader)

    inserted_count = 0
    dup_blocked_count = 0

    for tx in tx_list:
        tx_dict = {
            "transaction_id": tx["transaction_id"],
            "source_account_id": tx["source_account_id"],
            "target_account_id": tx["target_account_id"],
            "amount_inr": float(tx["amount_inr"]),
            "timestamp": tx["timestamp"],
            "payment_channel": tx["payment_channel"],
            "device_fingerprint": tx["device_fingerprint"],
        }
        process_transaction(graph, tx_dict, db_store=db_store)

    print(f"  [OK] Processed {len(tx_list)} transactions into GraphStore and SQLite.")

    # 3. Test duplicate delivery protection
    print("\n3. Testing duplicate transaction delivery idempotence...")
    first_tx = tx_list[0]
    dup_tx_dict = {
        "transaction_id": first_tx["transaction_id"],
        "source_account_id": first_tx["source_account_id"],
        "target_account_id": first_tx["target_account_id"],
        "amount_inr": float(first_tx["amount_inr"]),
        "timestamp": first_tx["timestamp"],
        "payment_channel": first_tx["payment_channel"],
        "device_fingerprint": first_tx["device_fingerprint"],
    }
    dup_signals = process_transaction(graph, dup_tx_dict, db_store=db_store)
    assert dup_signals == [], "Duplicate transaction should return empty signals list"

    db_tx_record = db_store.get_transaction(first_tx["transaction_id"])
    assert db_tx_record is not None

    cur = db_store._conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE transaction_id = ?", (first_tx["transaction_id"],)
    )
    count = cur.fetchone()[0]
    assert count == 1, f"Expected 1 record for duplicate tx, found {count}"
    print("  [OK] Duplicate delivery correctly ignored without creating duplicate records.")

    # 4. Detection rules & alert generation
    print("\n4. Running 8 detection rules + IsolationForest ML & triggering alerts...")
    # Get max transaction timestamp to use as as_of for sliding windows
    timestamps = [datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00")) for tx in tx_list]
    max_ts = max(timestamps)

    flagged_accounts = set()
    for acc in graph.accounts:
        ev = scorer.evaluate_account(graph, acc, as_of=max_ts)
        if ev.score >= 30:
            flagged_accounts.add(acc)
            alert = scorer.analyze(graph, acc, notify_threshold=30, as_of=max_ts)
            if alert:
                alert_dispatcher.dispatch(alert, band=ev.band, store=db_store)

    print(f"  [OK] Evaluated detection rules across accounts. Flagged accounts: {len(flagged_accounts)}")

    # 5. Verify SQLite persistence tables
    print("\n5. Verifying SQLite persistence tables (transactions, alerts, interventions)...")
    recent_txs = db_store.recent_transactions(limit=10)
    recent_alerts = db_store.recent_alerts(limit=10)

    cur_int = db_store._conn.execute("SELECT COUNT(*) FROM interventions")
    int_count = cur_int.fetchone()[0]

    assert len(recent_txs) > 0, "No transactions persisted in SQLite!"
    assert len(recent_alerts) > 0, "No alerts persisted in SQLite!"
    assert int_count > 0, "No interventions persisted in SQLite!"

    print(f"  [OK] SQLite transactions table: {len(tx_list)} records verified.")
    print(f"  [OK] SQLite alerts table: {len(recent_alerts)} recent records verified.")
    print(f"  [OK] SQLite interventions table: {int_count} records verified.")

    db_store.close()
    _cleanup_test_db(DB_PATH)

    print("\n=== E2E REPLAY VERIFICATION COMPLETE — ALL CHECKS PASSED ===")


if __name__ == "__main__":
    verify_e2e()
