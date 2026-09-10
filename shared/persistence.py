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

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    flagged_account_id TEXT NOT NULL,
    state TEXT NOT NULL,
    risk_score REAL NOT NULL,
    confidence REAL,
    band TEXT,
    suspicious_amount REAL NOT NULL,
    protected_amount REAL NOT NULL,
    existing_balance REAL NOT NULL,
    money_trail_json TEXT,
    predicted_terminals_json TEXT,
    predicted_window_start TEXT,
    predicted_window_end TEXT,
    evidence_json TEXT,
    bank_hold_status TEXT,
    terminal_block_status TEXT,
    lea_notification_status TEXT,
    withdrawal_attempts_json TEXT,
    complaint_id TEXT,
    escalation_level INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS selective_holds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    existing_balance REAL NOT NULL,
    suspicious_amount REAL NOT NULL,
    protected_amount REAL NOT NULL,
    source_transaction_id TEXT,
    chain_reference TEXT,
    reason TEXT,
    intervention_type TEXT,
    status TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS terminal_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    terminal_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    account_id TEXT,
    reason TEXT,
    action TEXT,
    valid_from TEXT,
    valid_until TEXT,
    status TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS withdrawal_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id TEXT UNIQUE NOT NULL,
    terminal_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    amount_inr REAL NOT NULL,
    timestamp TEXT NOT NULL,
    correlated_case_id TEXT,
    is_blocked INTEGER DEFAULT 0,
    action_taken TEXT,
    distance_to_predicted_km REAL,
    details_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS terminal_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    terminal_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS confirmations (
    confirmation_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    originating_account_id TEXT NOT NULL,
    destination_account_id TEXT NOT NULL,
    amount_inr REAL NOT NULL,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    responded_at TEXT,
    expires_at TEXT,
    outcome TEXT,
    case_id TEXT,
    intervention_state TEXT,
    downstream_transaction_ids_json TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recovery_workflows (
    workflow_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    originating_transaction_id TEXT NOT NULL,
    fraud_amount REAL NOT NULL,
    recovered_or_held_amount REAL NOT NULL,
    affected_accounts_json TEXT,
    action_items_json TEXT,
    status TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transaction_chains (
    chain_id TEXT PRIMARY KEY,
    root_transaction_id TEXT NOT NULL,
    origin_account_id TEXT NOT NULL,
    destination_account_chain_json TEXT,
    original_amount REAL NOT NULL,
    traceable_transactions_json TEXT,
    current_known_accounts_json TEXT,
    known_withdrawals_json TEXT,
    traceable_exposed_amounts_json TEXT,
    chain_depth INTEGER DEFAULT 1,
    chain_status TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chain_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id TEXT NOT NULL,
    parent_transaction_id TEXT,
    child_transaction_id TEXT NOT NULL,
    from_account_id TEXT NOT NULL,
    to_account_id TEXT NOT NULL,
    amount_inr REAL NOT NULL,
    payment_channel TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    hop_depth INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(chain_id, child_transaction_id)
);

CREATE TABLE IF NOT EXISTS account_exposures (
    account_id TEXT PRIMARY KEY,
    legitimate_balance REAL NOT NULL,
    suspicious_exposure REAL NOT NULL,
    total_balance REAL NOT NULL,
    contributing_root_transactions_json TEXT,
    active_chains_json TEXT,
    last_updated TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recovery_cases (
    case_id TEXT PRIMARY KEY,
    root_transaction_id TEXT NOT NULL,
    chain_id TEXT NOT NULL,
    origin_account TEXT NOT NULL,
    destination_account_chain_json TEXT,
    original_amount REAL NOT NULL,
    traceable_transactions_json TEXT,
    current_known_accounts_json TEXT,
    known_withdrawals_json TEXT,
    traceable_exposed_amounts_json TEXT,
    recovery_status TEXT NOT NULL,
    recovered_amount REAL DEFAULT 0.0,
    simulated_actions_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
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

    def save_case(self, case: Any) -> None:
        """Persist or update a CaseRecord in SQLite."""
        if hasattr(case, "to_dict"):
            data = case.to_dict()
        elif isinstance(case, dict):
            data = case
        else:
            raise TypeError(f"Expected dict or CaseRecord, got: {type(case)}")

        self._conn.execute(
            """INSERT OR REPLACE INTO cases
               (case_id, flagged_account_id, state, risk_score, confidence, band,
                suspicious_amount, protected_amount, existing_balance,
                money_trail_json, predicted_terminals_json, predicted_window_start, predicted_window_end,
                evidence_json, bank_hold_status, terminal_block_status, lea_notification_status,
                withdrawal_attempts_json, complaint_id, escalation_level, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(data["case_id"]),
                str(data["flagged_account_id"]),
                str(data.get("state", "PRE_COMPLAINT_INTERVENTION")),
                float(data.get("risk_score", 0.0)),
                float(data.get("confidence", 0.0)) if data.get("confidence") is not None else None,
                str(data.get("band", "HIGH")),
                float(data.get("suspicious_amount", 0.0)),
                float(data.get("protected_amount", 0.0)),
                float(data.get("existing_balance", 0.0)),
                json.dumps(data.get("money_trail", [])),
                json.dumps(data.get("predicted_terminals", [])),
                str(data.get("predicted_window_start", "")),
                str(data.get("predicted_window_end", "")),
                json.dumps(list(data.get("evidence", []))),
                str(data.get("bank_hold_status", "NONE")),
                str(data.get("terminal_block_status", "NONE")),
                str(data.get("lea_notification_status", "NONE")),
                json.dumps(list(data.get("withdrawal_attempts", []))),
                data.get("complaint_id"),
                int(data.get("escalation_level", 1)),
                str(data.get("created_at", "")),
                str(data.get("updated_at", "")),
            ),
        )
        self._conn.commit()

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute("SELECT * FROM cases WHERE case_id = ?", (str(case_id),))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        for json_col in ("money_trail", "predicted_terminals", "evidence", "withdrawal_attempts"):
            json_key = f"{json_col}_json"
            if rec.get(json_key):
                try:
                    val = json.loads(rec[json_key])
                    rec[json_col] = val
                    rec[json_key] = val
                except Exception:
                    pass
        return rec

    def recent_cases(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM cases ORDER BY updated_at DESC, created_at DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cur.description]
        rows = []
        for r in cur.fetchall():
            rec = dict(zip(cols, r))
            for json_col in ("money_trail", "predicted_terminals", "evidence", "withdrawal_attempts"):
                json_key = f"{json_col}_json"
                if rec.get(json_key):
                    try:
                        val = json.loads(rec[json_key])
                        rec[json_col] = val
                        rec[json_key] = val
                    except Exception:
                        pass
            rows.append(rec)
        return rows

    def save_selective_hold(self, hold: Any) -> None:
        """Persist a SelectiveFundProtection record into SQLite."""
        if hasattr(hold, "to_dict"):
            data = hold.to_dict()
        elif isinstance(hold, dict):
            data = hold
        else:
            raise TypeError(f"Expected dict or SelectiveFundProtection, got: {type(hold)}")

        self._conn.execute(
            """INSERT INTO selective_holds
               (case_id, account_id, existing_balance, suspicious_amount, protected_amount,
                source_transaction_id, chain_reference, reason, intervention_type, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(data["case_id"]),
                str(data["account_id"]),
                float(data.get("existing_balance", 0.0)),
                float(data.get("suspicious_amount", 0.0)),
                float(data.get("protected_amount", 0.0)),
                str(data.get("source_transaction_id", "")),
                str(data.get("chain_reference", "")),
                str(data.get("reason", "")),
                str(data.get("intervention_type", "PROVISIONAL_HOLD")),
                str(data.get("status", "ACTIVE")),
                str(data.get("timestamp", data.get("created_at", ""))),
            ),
        )
        self._conn.commit()

    def get_selective_holds(self, account_id: Optional[str] = None, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM selective_holds WHERE 1=1"
        params = []
        if account_id:
            query += " AND account_id = ?"
            params.append(str(account_id))
        if case_id:
            query += " AND case_id = ?"
            params.append(str(case_id))
        query += " ORDER BY id DESC"
        cur = self._conn.execute(query, tuple(params))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def save_terminal_block(self, req: Any) -> None:
        """Persist a TerminalBlockRequest into SQLite."""
        if hasattr(req, "to_dict"):
            data = req.to_dict()
        elif isinstance(req, dict):
            data = req
        else:
            raise TypeError(f"Expected dict or TerminalBlockRequest, got: {type(req)}")

        self._conn.execute(
            """INSERT INTO terminal_blocks
               (terminal_id, case_id, account_id, reason, action, valid_from, valid_until, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                str(data["terminal_id"]),
                str(data["case_id"]),
                str(data.get("account_id", "")),
                str(data.get("reason", "PREDICTED_CASH_EGRESS")),
                str(data.get("action", "BLOCK_WITHDRAWAL")),
                str(data.get("valid_from", "")),
                str(data.get("valid_until", "")),
                str(data.get("status", "REQUESTED")),
            ),
        )
        self._conn.commit()

    def get_active_terminal_blocks(self, terminal_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM terminal_blocks WHERE status IN ('REQUESTED', 'ACTIVE')"
        params = []
        if terminal_id:
            query += " AND terminal_id = ?"
            params.append(str(terminal_id))
        query += " ORDER BY id DESC"
        cur = self._conn.execute(query, tuple(params))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def save_withdrawal_attempt(self, attempt: Any) -> None:
        """Persist an attempted withdrawal event into SQLite."""
        if hasattr(attempt, "to_dict"):
            data = attempt.to_dict()
        elif isinstance(attempt, dict):
            data = attempt
        else:
            raise TypeError(f"Expected dict or WithdrawalAttemptEvent, got: {type(attempt)}")

        self._conn.execute(
            """INSERT OR REPLACE INTO withdrawal_attempts
               (attempt_id, terminal_id, account_id, amount_inr, timestamp,
                correlated_case_id, is_blocked, action_taken, distance_to_predicted_km, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(data["attempt_id"]),
                str(data["terminal_id"]),
                str(data["account_id"]),
                float(data.get("amount_inr", 0.0)),
                str(data.get("timestamp", "")),
                data.get("correlated_case_id"),
                int(bool(data.get("is_blocked", False))),
                str(data.get("action_taken", "MONITORED")),
                float(data.get("distance_to_predicted_km", 0.0)) if data.get("distance_to_predicted_km") is not None else None,
                json.dumps(data.get("nearby_terminals", [])),
            ),
        )
        self._conn.commit()

    def get_withdrawal_attempts(self, terminal_id: Optional[str] = None, account_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        query = "SELECT * FROM withdrawal_attempts WHERE 1=1"
        params = []
        if terminal_id:
            query += " AND terminal_id = ?"
            params.append(str(terminal_id))
        if account_id:
            query += " AND account_id = ?"
            params.append(str(account_id))
        query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(limit)
        cur = self._conn.execute(query, tuple(params))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_withdrawal_attempt(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM withdrawal_attempts WHERE attempt_id = ?",
            (str(attempt_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        if rec.get("details_json"):
            rec["nearby_terminals"] = json.loads(rec["details_json"])
        return rec

    def record_terminal_activity(self, account_id: str, terminal_id: str, timestamp: str) -> int:
        """Record account usage at a physical terminal and return total count for that pair."""
        self._conn.execute(
            "INSERT INTO terminal_activity (account_id, terminal_id, timestamp) VALUES (?, ?, ?)",
            (str(account_id), str(terminal_id), str(timestamp)),
        )
        self._conn.commit()
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM terminal_activity WHERE account_id = ? AND terminal_id = ?",
            (str(account_id), str(terminal_id)),
        )
        return cur.fetchone()[0]

    def get_terminal_activity_count(self, account_id: str, terminal_id: str) -> int:
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM terminal_activity WHERE account_id = ? AND terminal_id = ?",
            (str(account_id), str(terminal_id)),
        )
        return cur.fetchone()[0]

    def save_confirmation(self, conf: Any) -> None:
        """Persist or update customer confirmation record."""
        data = conf.to_dict() if hasattr(conf, "to_dict") else dict(conf)
        self._conn.execute(
            """
            INSERT INTO confirmations (
                confirmation_id, transaction_id, originating_account_id, destination_account_id,
                amount_inr, status, requested_at, responded_at, expires_at, outcome, case_id,
                intervention_state, downstream_transaction_ids_json, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(confirmation_id) DO UPDATE SET
                status = excluded.status,
                responded_at = excluded.responded_at,
                expires_at = excluded.expires_at,
                outcome = excluded.outcome,
                case_id = excluded.case_id,
                intervention_state = excluded.intervention_state,
                downstream_transaction_ids_json = excluded.downstream_transaction_ids_json,
                notes = excluded.notes,
                updated_at = datetime('now')
            """,
            (
                str(data["confirmation_id"]),
                str(data["transaction_id"]),
                str(data["originating_account_id"]),
                str(data["destination_account_id"]),
                float(data["amount_inr"]),
                str(data["status"]),
                str(data["requested_at"]),
                str(data["responded_at"]) if data.get("responded_at") else None,
                str(data["expires_at"]) if data.get("expires_at") else None,
                str(data["outcome"]) if data.get("outcome") else None,
                str(data["case_id"]) if data.get("case_id") else None,
                str(data.get("intervention_state", "PROVISIONAL_MONITORING")),
                json.dumps(data.get("downstream_transaction_ids", [])),
                str(data.get("notes", "")),
            ),
        )
        self._conn.commit()

    def get_confirmation(self, confirmation_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM confirmations WHERE confirmation_id = ?",
            (str(confirmation_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        if rec.get("downstream_transaction_ids_json"):
            rec["downstream_transaction_ids"] = json.loads(rec["downstream_transaction_ids_json"])
        else:
            rec["downstream_transaction_ids"] = []
        return rec

    def get_confirmation_by_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM confirmations WHERE transaction_id = ? ORDER BY created_at DESC LIMIT 1",
            (str(transaction_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        if rec.get("downstream_transaction_ids_json"):
            rec["downstream_transaction_ids"] = json.loads(rec["downstream_transaction_ids_json"])
        else:
            rec["downstream_transaction_ids"] = []
        return rec

    def get_pending_confirmations(self) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM confirmations WHERE status = 'PENDING_CONFIRMATION' ORDER BY requested_at ASC"
        )
        cols = [d[0] for d in cur.description]
        results = []
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            if rec.get("downstream_transaction_ids_json"):
                rec["downstream_transaction_ids"] = json.loads(rec["downstream_transaction_ids_json"])
            else:
                rec["downstream_transaction_ids"] = []
            results.append(rec)
        return results

    def recent_confirmations(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM confirmations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        results = []
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            if rec.get("downstream_transaction_ids_json"):
                rec["downstream_transaction_ids"] = json.loads(rec["downstream_transaction_ids_json"])
            else:
                rec["downstream_transaction_ids"] = []
            results.append(rec)
        return results

    def save_recovery_workflow(self, workflow: Any) -> None:
        """Persist or update recovery workflow record."""
        data = workflow.to_dict() if hasattr(workflow, "to_dict") else dict(workflow)
        self._conn.execute(
            """
            INSERT INTO recovery_workflows (
                workflow_id, case_id, originating_transaction_id, fraud_amount,
                recovered_or_held_amount, affected_accounts_json, action_items_json,
                status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(workflow_id) DO UPDATE SET
                recovered_or_held_amount = excluded.recovered_or_held_amount,
                affected_accounts_json = excluded.affected_accounts_json,
                action_items_json = excluded.action_items_json,
                status = excluded.status,
                updated_at = datetime('now')
            """,
            (
                str(data["workflow_id"]),
                str(data["case_id"]),
                str(data["originating_transaction_id"]),
                float(data["fraud_amount"]),
                float(data.get("recovered_or_held_amount", 0.0)),
                json.dumps(data.get("affected_accounts", [])),
                json.dumps(data.get("action_items", [])),
                str(data.get("status", "INITIATED")),
            ),
        )
        self._conn.commit()

    def get_recovery_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM recovery_workflows WHERE workflow_id = ?",
            (str(workflow_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        if rec.get("affected_accounts_json"):
            rec["affected_accounts"] = json.loads(rec["affected_accounts_json"])
        if rec.get("action_items_json"):
            rec["action_items"] = json.loads(rec["action_items_json"])
        return rec

    def get_recovery_workflow_by_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM recovery_workflows WHERE case_id = ? ORDER BY created_at DESC LIMIT 1",
            (str(case_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        if rec.get("affected_accounts_json"):
            rec["affected_accounts"] = json.loads(rec["affected_accounts_json"])
        if rec.get("action_items_json"):
            rec["action_items"] = json.loads(rec["action_items_json"])
        return rec

    def recent_recovery_workflows(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM recovery_workflows ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        results = []
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            if rec.get("affected_accounts_json"):
                rec["affected_accounts"] = json.loads(rec["affected_accounts_json"])
            if rec.get("action_items_json"):
                rec["action_items"] = json.loads(rec["action_items_json"])
            results.append(rec)
        return results

    # ------------------------------------------------------------------------
    # Part 2: Fund Traceability & Recovery Persistence
    # ------------------------------------------------------------------------

    def save_chain(self, chain: Any) -> None:
        """Persist or update transaction provenance chain record."""
        data = chain.to_dict() if hasattr(chain, "to_dict") else dict(chain)
        self._conn.execute(
            """
            INSERT INTO transaction_chains (
                chain_id, root_transaction_id, origin_account_id,
                destination_account_chain_json, original_amount, traceable_transactions_json,
                current_known_accounts_json, known_withdrawals_json, traceable_exposed_amounts_json,
                chain_depth, chain_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(chain_id) DO UPDATE SET
                destination_account_chain_json = excluded.destination_account_chain_json,
                traceable_transactions_json = excluded.traceable_transactions_json,
                current_known_accounts_json = excluded.current_known_accounts_json,
                known_withdrawals_json = excluded.known_withdrawals_json,
                traceable_exposed_amounts_json = excluded.traceable_exposed_amounts_json,
                chain_depth = excluded.chain_depth,
                chain_status = excluded.chain_status,
                updated_at = datetime('now')
            """,
            (
                str(data["chain_id"]),
                str(data["root_transaction_id"]),
                str(data["origin_account_id"]),
                json.dumps(data.get("destination_account_chain", [])),
                float(data["original_amount"]),
                json.dumps(data.get("traceable_transactions", [])),
                json.dumps(data.get("current_known_accounts", [])),
                json.dumps(data.get("known_withdrawals", [])),
                json.dumps(data.get("traceable_exposed_amounts", {})),
                int(data.get("chain_depth", 1)),
                str(data.get("chain_status", "ACTIVE")),
            ),
        )
        self._conn.commit()

    def _hydrate_chain(self, cur, row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        if rec.get("destination_account_chain_json"):
            rec["destination_account_chain"] = json.loads(rec["destination_account_chain_json"])
        if rec.get("traceable_transactions_json"):
            rec["traceable_transactions"] = json.loads(rec["traceable_transactions_json"])
        if rec.get("current_known_accounts_json"):
            rec["current_known_accounts"] = json.loads(rec["current_known_accounts_json"])
        if rec.get("known_withdrawals_json"):
            rec["known_withdrawals"] = json.loads(rec["known_withdrawals_json"])
        if rec.get("traceable_exposed_amounts_json"):
            rec["traceable_exposed_amounts"] = json.loads(rec["traceable_exposed_amounts_json"])
        return rec

    def get_chain(self, chain_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM transaction_chains WHERE chain_id = ?",
            (str(chain_id),),
        )
        return self._hydrate_chain(cur, cur.fetchone())

    def get_chain_by_root_tx(self, root_transaction_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM transaction_chains WHERE root_transaction_id = ? ORDER BY created_at DESC LIMIT 1",
            (str(root_transaction_id),),
        )
        return self._hydrate_chain(cur, cur.fetchone())

    def recent_chains(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM transaction_chains ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [self._hydrate_chain(cur, r) for r in rows if r]

    def save_chain_edge(self, edge: Any) -> bool:
        """Persist a single child/edge in a chain idempotently."""
        data = edge.to_dict() if hasattr(edge, "to_dict") else dict(edge)
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO chain_edges (
                chain_id, parent_transaction_id, child_transaction_id, from_account_id,
                to_account_id, amount_inr, payment_channel, timestamp, hop_depth
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(data["chain_id"]),
                str(data["parent_transaction_id"]) if data.get("parent_transaction_id") else None,
                str(data["child_transaction_id"]),
                str(data["from_account_id"]),
                str(data["to_account_id"]),
                float(data["amount_inr"]),
                str(data["payment_channel"]),
                str(data["timestamp"]),
                int(data.get("hop_depth", 1)),
            ),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_chain_edges(self, chain_id: str) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM chain_edges WHERE chain_id = ? ORDER BY hop_depth ASC, created_at ASC",
            (str(chain_id),),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def save_account_exposure(self, exposure: Any) -> None:
        """Persist or update an account's exposure and legitimate balances."""
        data = exposure.to_dict() if hasattr(exposure, "to_dict") else dict(exposure)
        self._conn.execute(
            """
            INSERT INTO account_exposures (
                account_id, legitimate_balance, suspicious_exposure, total_balance,
                contributing_root_transactions_json, active_chains_json, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(account_id) DO UPDATE SET
                legitimate_balance = excluded.legitimate_balance,
                suspicious_exposure = excluded.suspicious_exposure,
                total_balance = excluded.total_balance,
                contributing_root_transactions_json = excluded.contributing_root_transactions_json,
                active_chains_json = excluded.active_chains_json,
                last_updated = datetime('now')
            """,
            (
                str(data["account_id"]),
                float(data.get("legitimate_balance", 0.0)),
                float(data.get("suspicious_exposure", 0.0)),
                float(data.get("total_balance", 0.0)),
                json.dumps(data.get("contributing_root_transactions", [])),
                json.dumps(data.get("active_chains", [])),
            ),
        )
        self._conn.commit()

    def get_account_exposure(self, account_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM account_exposures WHERE account_id = ?",
            (str(account_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        if rec.get("contributing_root_transactions_json"):
            rec["contributing_root_transactions"] = json.loads(rec["contributing_root_transactions_json"])
        if rec.get("active_chains_json"):
            rec["active_chains"] = json.loads(rec["active_chains_json"])
        return rec

    def recent_account_exposures(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM account_exposures ORDER BY last_updated DESC LIMIT ?",
            (limit,),
        )
        cols = [d[0] for d in cur.description]
        results = []
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            if rec.get("contributing_root_transactions_json"):
                rec["contributing_root_transactions"] = json.loads(rec["contributing_root_transactions_json"])
            if rec.get("active_chains_json"):
                rec["active_chains"] = json.loads(rec["active_chains_json"])
            results.append(rec)
        return results

    def save_recovery_case(self, case: Any) -> None:
        """Persist or update formal recovery case record."""
        data = case.to_dict() if hasattr(case, "to_dict") else dict(case)
        self._conn.execute(
            """
            INSERT INTO recovery_cases (
                case_id, root_transaction_id, chain_id, origin_account,
                destination_account_chain_json, original_amount, traceable_transactions_json,
                current_known_accounts_json, known_withdrawals_json, traceable_exposed_amounts_json,
                recovery_status, recovered_amount, simulated_actions_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(case_id) DO UPDATE SET
                destination_account_chain_json = excluded.destination_account_chain_json,
                traceable_transactions_json = excluded.traceable_transactions_json,
                current_known_accounts_json = excluded.current_known_accounts_json,
                known_withdrawals_json = excluded.known_withdrawals_json,
                traceable_exposed_amounts_json = excluded.traceable_exposed_amounts_json,
                recovery_status = excluded.recovery_status,
                recovered_amount = excluded.recovered_amount,
                simulated_actions_json = excluded.simulated_actions_json,
                updated_at = datetime('now')
            """,
            (
                str(data["case_id"]),
                str(data["root_transaction_id"]),
                str(data["chain_id"]),
                str(data["origin_account"]),
                json.dumps(data.get("destination_account_chain", [])),
                float(data["original_amount"]),
                json.dumps(data.get("traceable_transactions", [])),
                json.dumps(data.get("current_known_accounts", [])),
                json.dumps(data.get("known_withdrawals", [])),
                json.dumps(data.get("traceable_exposed_amounts", {})),
                str(data.get("recovery_status", "NOT_STARTED")),
                float(data.get("recovered_amount", 0.0)),
                json.dumps(data.get("simulated_actions", [])),
            ),
        )
        self._conn.commit()

    def _hydrate_recovery_case(self, cur, row) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        rec = dict(zip(cols, row))
        if rec.get("destination_account_chain_json"):
            rec["destination_account_chain"] = json.loads(rec["destination_account_chain_json"])
        if rec.get("traceable_transactions_json"):
            rec["traceable_transactions"] = json.loads(rec["traceable_transactions_json"])
        if rec.get("current_known_accounts_json"):
            rec["current_known_accounts"] = json.loads(rec["current_known_accounts_json"])
        if rec.get("known_withdrawals_json"):
            rec["known_withdrawals"] = json.loads(rec["known_withdrawals_json"])
        if rec.get("traceable_exposed_amounts_json"):
            rec["traceable_exposed_amounts"] = json.loads(rec["traceable_exposed_amounts_json"])
        if rec.get("simulated_actions_json"):
            rec["simulated_actions"] = json.loads(rec["simulated_actions_json"])
        return rec

    def get_recovery_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM recovery_cases WHERE case_id = ?",
            (str(case_id),),
        )
        return self._hydrate_recovery_case(cur, cur.fetchone())

    def get_recovery_case_by_root_tx(self, root_tx_id: str) -> Optional[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM recovery_cases WHERE root_transaction_id = ? ORDER BY created_at DESC LIMIT 1",
            (str(root_tx_id),),
        )
        return self._hydrate_recovery_case(cur, cur.fetchone())

    def recent_recovery_cases(self, limit: int = 20) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM recovery_cases ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [self._hydrate_recovery_case(cur, r) for r in rows if r]

    def close(self) -> None:
        self._conn.close()


