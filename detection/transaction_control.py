"""detection/transaction_control.py — Confirmation & Transaction Control Layer for SIH26184.

Implements the fine-grained confirmation and channel-differentiated intervention controls:
1. PENDING_CONFIRMATION for high-value/unusual transfers without blunt premature account freezing.
2. Downstream online transfers (UPI/IMPS/NEFT/RTGS) remain ALLOWED + MONITORED during pending confirmation.
3. Cash egress (ATM, AEPS, Micro-ATM, POS) attempting to withdraw suspicious funds is RESTRICTED/INTERCEPTED
   while pre-existing legitimate balance remains usable.
4. CONFIRMED_LEGITIMATE: Clears temporary restrictions without leaving stale holds.
5. CONFIRMED_FRAUD: Traces the downstream chain, escalates investigation, places selective holds,
   blocks terminal egress, and triggers recovery workflow.
6. EXPIRED / NO_RESPONSE: Graceful timeout handling preserving audit logs and monitoring without auto-fraud.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any

from audit.blockchain_lite import AuditLedger
from pipeline.graph_store import GraphStore
from shared.persistence import Store
from shared.schemas import (
    ConfirmationRecord,
    ConfirmationStatus,
    ControlAction,
    RecoveryWorkflowRecord,
    TransactionChannel,
    TransactionControlDecision,
)

log = logging.getLogger("transaction_control")


class TransactionControlManager:
    """Manages transaction-level confirmation lifecycles and fine-grained channel controls."""

    def __init__(
        self,
        store: Optional[Store] = None,
        graph_store: Optional[GraphStore] = None,
        ledger: Optional[AuditLedger] = None,
    ) -> None:
        self.store = store or Store()
        self.graph_store = graph_store or GraphStore()
        self.ledger = ledger or AuditLedger()

    def request_confirmation(
        self,
        transaction_id: str,
        sender_id: str,
        beneficiary_id: str,
        amount: float,
        reason: str = "High-value or anomalous transfer requiring customer confirmation",
        timeout_seconds: int = 300,
        case_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConfirmationRecord:
        """Create a new confirmation request in PENDING_CONFIRMATION state."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=timeout_seconds)
        conf_id = f"CONF-{transaction_id}"
        cid = case_id or f"CASE-{transaction_id}"

        record = ConfirmationRecord(
            confirmation_id=conf_id,
            transaction_id=transaction_id,
            originating_account_id=sender_id,
            destination_account_id=beneficiary_id,
            amount_inr=float(amount),
            status=ConfirmationStatus.PENDING_CONFIRMATION,
            requested_at=now,
            expires_at=expires_at,
            case_id=cid,
            intervention_state="PROVISIONAL_MONITORING",
            downstream_transaction_ids=[],
            notes=reason,
        )

        self.store.save_confirmation(record)

        self.ledger.append({
            "event": "CONFIRMATION_REQUESTED",
            "confirmation_id": record.confirmation_id,
            "transaction_id": record.transaction_id,
            "originating_account_id": record.originating_account_id,
            "destination_account_id": record.destination_account_id,
            "amount_inr": record.amount_inr,
            "status": record.status,
            "reason": record.notes,
            "case_id": record.case_id,
            "expires_at": record.expires_at.isoformat() if isinstance(record.expires_at, datetime) else str(record.expires_at),
        })
        log.info(f"[CONFIRMATION_REQUESTED] {record.confirmation_id} for tx {transaction_id} (₹{amount:,.2f}) -> {record.status}")
        return record

    def check_timeouts(self) -> List[Dict[str, Any]]:
        """Check all pending confirmations and transition expired ones to EXPIRED."""
        pending = self.store.get_pending_confirmations()
        now_dt = datetime.now(timezone.utc)
        expired_records: List[Dict[str, Any]] = []

        for record in pending:
            exp_str = record.get("expires_at")
            if not exp_str:
                continue
            try:
                exp_dt = datetime.fromisoformat(str(exp_str))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            if now_dt >= exp_dt:
                record["status"] = ConfirmationStatus.EXPIRED
                record["responded_at"] = now_dt.isoformat()
                record["outcome"] = "TIMEOUT_EXPIRED"
                record["notes"] = (record.get("notes") or "") + " [System: confirmation window expired with no response]"
                self.store.save_confirmation(record)
                expired_records.append(record)

                self.ledger.append({
                    "event": "CONFIRMATION_EXPIRED",
                    "confirmation_id": record["confirmation_id"],
                    "transaction_id": record["transaction_id"],
                    "status": record["status"],
                    "case_id": record.get("case_id"),
                })
                log.info(f"[CONFIRMATION_EXPIRED] {record['confirmation_id']} timed out without response.")

        return expired_records

    def submit_confirmation_response(
        self,
        confirmation_id: str,
        response_status: str,
        notes: str = "",
        responder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a response (CONFIRMED_LEGITIMATE or CONFIRMED_FRAUD) to a confirmation request."""
        self.check_timeouts()

        record = self.store.get_confirmation(confirmation_id)
        if not record:
            raise KeyError(f"Confirmation request not found: {confirmation_id}")

        current_status = record.get("status")
        # Idempotency check: if already finalized with same status, return existing record
        if current_status == response_status:
            return record

        now = datetime.now(timezone.utc).isoformat()
        record["status"] = response_status
        record["responded_at"] = now
        record["notes"] = f"{record.get('notes', '')} | Response: {notes}".strip(" |")
        record["outcome"] = "LEGITIMATE_CLEARED" if response_status == ConfirmationStatus.CONFIRMED_LEGITIMATE else "FRAUD_ESCALATED"
        record["intervention_state"] = "UNENCUMBERED" if response_status == ConfirmationStatus.CONFIRMED_LEGITIMATE else "FUNDS_HELD"

        self.store.save_confirmation(record)

        self.ledger.append({
            "event": "CONFIRMATION_RESPONDED",
            "confirmation_id": record["confirmation_id"],
            "transaction_id": record["transaction_id"],
            "status": response_status,
            "notes": notes,
            "responder_id": responder_id,
            "responded_at": now,
        })

        if response_status == ConfirmationStatus.CONFIRMED_FRAUD:
            self._handle_confirmed_fraud(record)
        elif response_status == ConfirmationStatus.CONFIRMED_LEGITIMATE:
            self._handle_confirmed_legitimate(record)

        return record

    def _handle_confirmed_fraud(self, record: Dict[str, Any]) -> RecoveryWorkflowRecord:
        """Trace downstream chain, initiate recovery workflow, and record selective holds."""
        beneficiary_id = record["destination_account_id"]
        amount = float(record["amount_inr"])
        tx_id = record["transaction_id"]
        case_id = record.get("case_id") or f"CASE-{tx_id}"

        legs = self.graph_store.reconstruct_downstream_chain(beneficiary_id, max_hops=8)
        downstream_txs = self.graph_store.get_downstream_transactions_from(beneficiary_id)

        affected_accounts = set([beneficiary_id])
        held_amounts: Dict[str, float] = {}

        # The primary destination account has the suspicious amount held if not further dispersed
        held_amounts[beneficiary_id] = amount

        for leg in legs:
            affected_accounts.add(leg.source_account_id)
            affected_accounts.add(leg.target_account_id)
            held_amounts[leg.target_account_id] = max(
                held_amounts.get(leg.target_account_id, 0.0), leg.amount_inr
            )

        # Track downstream transaction IDs and affected accounts
        downstream_tx_ids = []
        for tx in downstream_txs:
            t_id = tx.transaction_id if hasattr(tx, "transaction_id") else tx.get("transaction_id")
            if t_id:
                downstream_tx_ids.append(t_id)

        # Update confirmation with discovered downstream transaction IDs
        record["downstream_transaction_ids"] = downstream_tx_ids
        self.store.save_confirmation(record)

        workflow_id = f"REC-{case_id}"
        total_held = sum(held_amounts.values()) if held_amounts else amount

        action_items = [
            {
                "action": "SELECTIVE_HOLD",
                "account_id": acc,
                "amount": held_amounts.get(acc, amount),
                "status": "APPLIED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for acc in affected_accounts
        ]
        action_items.append({
            "action": "TERMINAL_BLOCK",
            "reason": "PREDICTED_CASH_EGRESS",
            "status": "APPLIED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        workflow = RecoveryWorkflowRecord(
            workflow_id=workflow_id,
            case_id=case_id,
            originating_transaction_id=tx_id,
            fraud_amount=amount,
            recovered_or_held_amount=total_held,
            affected_accounts=list(affected_accounts),
            action_items=action_items,
            status="INITIATED",
        )

        self.store.save_recovery_workflow(workflow)

        self.ledger.append({
            "event": "RECOVERY_WORKFLOW_INITIATED",
            "workflow_id": workflow.workflow_id,
            "case_id": workflow.case_id,
            "fraud_amount": workflow.fraud_amount,
            "recovered_or_held_amount": workflow.recovered_or_held_amount,
            "affected_accounts": workflow.affected_accounts,
            "chain_hops": len(legs),
        })

        log.info(f"[CONFIRMED_FRAUD] Initiated recovery workflow {workflow_id} for case {workflow.case_id}")
        return workflow

    def _handle_confirmed_legitimate(self, record: Dict[str, Any]) -> None:
        """Clear provisional holds and record legitimate status."""
        self.ledger.append({
            "event": "CONFIRMATION_CLEARED_LEGITIMATE",
            "confirmation_id": record["confirmation_id"],
            "transaction_id": record["transaction_id"],
            "case_id": record.get("case_id"),
            "unencumbered_account": record["destination_account_id"],
        })
        log.info(f"[CONFIRMED_LEGITIMATE] Cleared provisional holds on {record['destination_account_id']} for tx {record['transaction_id']}")

    def evaluate_transaction_control(
        self,
        transaction_id: str,
        from_account: str,
        to_account: str,
        amount: float,
        channel_or_type: str,
        timestamp: Optional[str] = None,
        existing_balance: float = 20000.0,
    ) -> TransactionControlDecision:
        """Evaluate whether a transaction or withdrawal should be ALLOWED, MONITORED, or RESTRICTED."""
        self.check_timeouts()

        channel = TransactionChannel.classify(channel_or_type)
        pending_confs = self.store.get_pending_confirmations()

        # Find if from_account is the beneficiary/destination of any pending confirmation
        relevant_pending: Optional[Dict[str, Any]] = None
        for conf in pending_confs:
            if conf.get("destination_account_id") == from_account:
                relevant_pending = conf
                break

        # Check if this account is flagged under confirmed fraud
        all_confs = self.store.recent_confirmations(limit=100)
        confirmed_fraud_for_account = any(
            c.get("status") == ConfirmationStatus.CONFIRMED_FRAUD and c.get("destination_account_id") == from_account
            for c in all_confs
        )

        if confirmed_fraud_for_account:
            return TransactionControlDecision(
                transaction_id=transaction_id,
                account_id=from_account,
                channel=channel,
                amount_inr=float(amount),
                action=ControlAction.RESTRICT,
                allowed=False,
                reason=f"Account {from_account} is subject to active recovery hold following confirmed fraud.",
                held_amount=amount,
                available_balance=0.0,
                correlated_case_id=relevant_pending.get("case_id") if relevant_pending else None,
                confirmation_id=relevant_pending.get("confirmation_id") if relevant_pending else None,
            )

        # If no pending confirmation relates to this account, normal flow
        if not relevant_pending:
            return TransactionControlDecision(
                transaction_id=transaction_id,
                account_id=from_account,
                channel=channel,
                amount_inr=float(amount),
                action=ControlAction.ALLOW,
                allowed=True,
                reason="Standard transaction: no active holds or pending confirmations.",
                held_amount=0.0,
                available_balance=existing_balance,
                correlated_case_id=None,
                confirmation_id=None,
            )

        suspicious_amount = float(relevant_pending["amount_inr"])

        # Case 1: Online transfer while confirmation is pending -> ALLOW + MONITOR
        if channel == TransactionChannel.ONLINE_TRANSFER:
            return TransactionControlDecision(
                transaction_id=transaction_id,
                account_id=from_account,
                channel=channel,
                amount_inr=float(amount),
                action=ControlAction.MONITOR,
                allowed=True,
                reason=(
                    f"Downstream online transfer ({channel_or_type}) ALLOWED and MONITORED "
                    f"while upstream transaction {relevant_pending['transaction_id']} is {relevant_pending['status']}."
                ),
                held_amount=0.0,
                available_balance=existing_balance + suspicious_amount,
                correlated_case_id=relevant_pending.get("case_id"),
                confirmation_id=relevant_pending.get("confirmation_id"),
            )

        # Case 2: Cash withdrawal / ATM egress while confirmation is pending
        if channel == TransactionChannel.CASH_WITHDRAWAL:
            # Check if attempting to withdraw more than legitimate existing balance
            if amount > existing_balance:
                # Attempting to drain suspicious funds
                return TransactionControlDecision(
                    transaction_id=transaction_id,
                    account_id=from_account,
                    channel=channel,
                    amount_inr=float(amount),
                    action=ControlAction.RESTRICT,
                    allowed=False,
                    reason=(
                        f"Cash withdrawal of ₹{amount:,.2f} RESTRICTED: exceeds legitimate balance (₹{existing_balance:,.2f}) "
                        f"and attempts egress of provisional funds (₹{suspicious_amount:,.2f}) under {relevant_pending['status']}."
                    ),
                    held_amount=suspicious_amount,
                    available_balance=existing_balance,
                    correlated_case_id=relevant_pending.get("case_id"),
                    confirmation_id=relevant_pending.get("confirmation_id"),
                )
            else:
                # Withdrawal fits within existing legitimate balance
                return TransactionControlDecision(
                    transaction_id=transaction_id,
                    account_id=from_account,
                    channel=channel,
                    amount_inr=float(amount),
                    action=ControlAction.ALLOW,
                    allowed=True,
                    reason=(
                        f"Cash withdrawal of ₹{amount:,.2f} ALLOWED from pre-existing legitimate balance "
                        f"(₹{existing_balance:,.2f}). Suspicious ₹{suspicious_amount:,.2f} remains protected under {relevant_pending['status']}."
                    ),
                    held_amount=suspicious_amount,
                    available_balance=existing_balance - amount,
                    correlated_case_id=relevant_pending.get("case_id"),
                    confirmation_id=relevant_pending.get("confirmation_id"),
                )

        return TransactionControlDecision(
            transaction_id=transaction_id,
            account_id=from_account,
            channel=channel,
            amount_inr=float(amount),
            action=ControlAction.ALLOW,
            allowed=True,
            reason="Transfer evaluated.",
        )
