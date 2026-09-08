"""shared/persistence.py — SQLite-backed alert/intervention store.

This is the "database architecture" piece from Part 2 (Streaming/Data
Infra), scoped realistically: SQLite, not a Postgres/Neo4j cluster, because a
prototype's job is to prove the data model, not survive production load. The
schema is deliberately the kind that translates directly onto Postgres later
(see Must-Read/Phases.md roadmap) — swapping the connection is the only
change that would be needed.

Two tables:
  alerts         — every RiskAlert ever produced (for replay + demo history)
  interventions  — every auto_intervention.Decision ever made (for audit)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "output" / "cybershield.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    source_account_id TEXT NOT NULL,
    target_account_id TEXT NOT NULL,
    amount_inr REAL NOT NULL,
    timestamp TEXT NOT NULL,
    payment_channel TEXT NOT NULL,
    device_fingerprint TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alerts (
    complaint_id TEXT PRIMARY KEY,
    flagged_account_id TEXT NOT NULL,
    risk_score REAL NOT NULL,
    confidence REAL,
    band TEXT,
    evidence_json TEXT,
    predicted_terminals_json TEXT,
    predicted_window_start TEXT,
    predicted_window_end TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interventions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id TEXT NOT NULL,
    tier TEXT NOT NULL,
    bank_action TEXT,
    lea_notified INTEGER,
    justification TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (complaint_id) REFERENCES alerts(complaint_id)
);
"""


class Store:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def save_transaction(self, tx: Any) -> bool:
        """Persist a transaction into SQLite.

        Accepts a dict or TransactionEvent object.
        Returns True if inserted, False if ignored as a duplicate (idempotent).
        """
        if hasattr(tx, "to_dict"):
            data = tx.to_dict()
        elif isinstance(tx, dict):
            data = tx
        else:
            raise TypeError(f"Expected dict or TransactionEvent, got: {type(tx)}")

        transaction_id = str(data["transaction_id"])
        source_account_id = str(data["source_account_id"])
        target_account_id = str(data["target_account_id"])
        amount_inr = float(data["amount_inr"])
        timestamp = str(data["timestamp"])
        payment_channel = str(data["payment_channel"])
        device_fingerprint = str(data.get("device_fingerprint", ""))

        cur = self._conn.execute(
            """INSERT OR IGNORE INTO transactions
               (transaction_id, source_account_id, target_account_id, amount_inr, timestamp, payment_channel, device_fingerprint)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                transaction_id,
                source_account_id,
                target_account_id,
                amount_inr,
                timestamp,
                payment_channel,
                device_fingerprint,
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?", (str(transaction_id),)
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

    def recent_transactions(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM transactions ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def save_alert(self, alert, band: str) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO alerts
               (complaint_id, flagged_account_id, risk_score, confidence, band,
                evidence_json, predicted_terminals_json, predicted_window_start, predicted_window_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert.complaint_id, alert.flagged_account_id, alert.risk_score, alert.confidence, band,
                json.dumps(list(alert.evidence)),
                json.dumps([t.to_dict() for t in alert.predicted_terminals]),
                str(alert.predicted_window_start), str(alert.predicted_window_end),
            ),
        )
        self._conn.commit()

    def save_intervention(self, complaint_id: str, decision) -> None:
        self._conn.execute(
            """INSERT INTO interventions
               (complaint_id, tier, bank_action, lea_notified, justification)
               VALUES (?, ?, ?, ?, ?)""",
            (complaint_id, decision.tier, decision.bank_action,
             int(bool(decision.lea_notified)), decision.justification),
        )
        self._conn.commit()

    def recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()
