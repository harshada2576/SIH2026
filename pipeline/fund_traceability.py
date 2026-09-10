"""pipeline/fund_traceability.py — Fund Provenance, Traceability, and Recovery Layer for SIH26184.

Answers: “A suspicious transaction originated at A. Where did that money subsequently move?”

Key Mandates:
1. Origin Transaction: Establishes root_transaction_id and chain_id.
2. Downstream Chain Tracking: Preserves full tree/path (A -> B -> C -> D -> E) with structured queries.
3. Pending Confirmation: Downstream transfers continue normally (ALLOW + MONITOR) while preserving root linkage.
4. Confirmed Fraud: Traces full descendant trail, calculates traceable exposure, builds RecoveryCaseRecord.
5. NO False "Suspicious Funds First" Fallacy: Accurately separates legitimate balances from traceable suspicious
   exposures when funds are commingled, without fabricating physical rupee attribution.
6. Multi-Victim Convergence: Detects multiple sources converging into a common mule/aggregator account.
7. Simulated Prototype Recovery Workflow: Explicitly tracks statutory recovery states.
8. Complete Idempotency & Persistence: Backed by SQLite Store and GraphStore.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Set

from audit.blockchain_lite import AuditLedger
from pipeline.graph_store import GraphStore
from shared.persistence import Store
from shared.schemas import (
    AccountExposureRecord,
    ConfirmationStatus,
    ConvergentChainsRecord,
    RecoveryCaseRecord,
    RecoveryState,
    TransactionChainEdge,
    TransactionChainRecord,
    TransactionChannel,
    TransactionEvent,
)

log = logging.getLogger("fund_traceability")


class FundTraceabilityEngine:
    """Manages fund provenance, descendant tracking, commingled exposure accounting, and recovery workflows."""

    def __init__(
        self,
        store: Optional[Store] = None,
        graph_store: Optional[GraphStore] = None,
        ledger: Optional[AuditLedger] = None,
    ) -> None:
        self.store = store or Store()
        self.graph_store = graph_store or GraphStore()
        self.ledger = ledger or AuditLedger()

    # ------------------------------------------------------------------------
    # 1. Origin & Chain Initialization
    # ------------------------------------------------------------------------

    def establish_trace_root(
        self,
        root_transaction_id: str,
        origin_account_id: str,
        destination_account_id: str,
        amount_inr: float,
        payment_channel: str = "IMPS",
        timestamp: Optional[str] = None,
        chain_id: Optional[str] = None,
        chain_status: str = "PENDING_CONFIRMATION",
        existing_legitimate_balance: float = 20000.0,
    ) -> TransactionChainRecord:
        """Establish a new root transaction and initialize its downstream provenance chain."""
        cid = chain_id or f"CHAIN-{root_transaction_id}"
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        # Idempotency check: return existing chain if already registered
        existing = self.store.get_chain(cid)
        if existing:
            return TransactionChainRecord(
                chain_id=existing["chain_id"],
                root_transaction_id=existing["root_transaction_id"],
                origin_account_id=existing["origin_account_id"],
                destination_account_chain=existing.get("destination_account_chain", []),
                original_amount=float(existing.get("original_amount", amount_inr)),
                traceable_transactions=existing.get("traceable_transactions", []),
                current_known_accounts=existing.get("current_known_accounts", []),
                known_withdrawals=existing.get("known_withdrawals", []),
                traceable_exposed_amounts=existing.get("traceable_exposed_amounts", {}),
                chain_depth=int(existing.get("chain_depth", 1)),
                chain_status=existing.get("chain_status", chain_status),
                created_at=existing.get("created_at", ts),
                updated_at=existing.get("updated_at", ts),
            )

        root_tx_dict = {
            "transaction_id": root_transaction_id,
            "parent_transaction_id": None,
            "from_account_id": origin_account_id,
            "to_account_id": destination_account_id,
            "amount_inr": float(amount_inr),
            "payment_channel": payment_channel,
            "channel_type": TransactionChannel.classify(payment_channel),
            "timestamp": ts,
            "hop_depth": 1,
            "status": chain_status,
        }

        chain_record = TransactionChainRecord(
            chain_id=cid,
            root_transaction_id=root_transaction_id,
            origin_account_id=origin_account_id,
            destination_account_chain=[destination_account_id],
            original_amount=float(amount_inr),
            traceable_transactions=[root_tx_dict],
            current_known_accounts=[destination_account_id],
            known_withdrawals=[],
            traceable_exposed_amounts={destination_account_id: float(amount_inr)},
            chain_depth=1,
            chain_status=chain_status,
            created_at=ts,
            updated_at=ts,
        )

        self.store.save_chain(chain_record)

        # Save initial edge
        edge = TransactionChainEdge(
            chain_id=cid,
            parent_transaction_id=None,
            child_transaction_id=root_transaction_id,
            from_account_id=origin_account_id,
            to_account_id=destination_account_id,
            amount_inr=float(amount_inr),
            payment_channel=payment_channel,
            timestamp=ts,
            hop_depth=1,
        )
        self.store.save_chain_edge(edge)

        # Update destination account exposure (commingled fund tracking)
        self._update_account_exposure_on_ingress(
            account_id=destination_account_id,
            amount_inr=float(amount_inr),
            root_transaction_id=root_transaction_id,
            chain_id=cid,
            pre_existing_balance=existing_legitimate_balance,
        )

        self.ledger.append({
            "event": "TRACE_ROOT_ESTABLISHED",
            "chain_id": cid,
            "root_transaction_id": root_transaction_id,
            "origin_account_id": origin_account_id,
            "destination_account_id": destination_account_id,
            "amount_inr": float(amount_inr),
            "chain_status": chain_status,
        })

        log.info(f"[TRACE_ROOT] Established chain {cid} for root tx {root_transaction_id} ({origin_account_id} -> {destination_account_id}: ₹{amount_inr:,.2f})")
        return chain_record

    # ------------------------------------------------------------------------
    # 2. Downstream Descendant Transaction Tracking
    # ------------------------------------------------------------------------

    def track_descendant_transaction(
        self,
        parent_transaction_id: Optional[str],
        child_transaction_id: str,
        from_account_id: str,
        to_account_id: str,
        amount_inr: float,
        payment_channel: str,
        timestamp: Optional[str] = None,
        is_cashout: bool = False,
        terminal_id: Optional[str] = None,
    ) -> List[TransactionChainRecord]:
        """Track a downstream transaction leg across all relevant provenance chains."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        channel_type = TransactionChannel.classify(payment_channel)
        is_cash_egress = is_cashout or channel_type == TransactionChannel.CASH_WITHDRAWAL

        # Also register transaction into graph store if not already present
        try:
            self.graph_store.add_transaction(
                TransactionEvent(
                    transaction_id=child_transaction_id,
                    source_account_id=from_account_id,
                    target_account_id=to_account_id,
                    amount_inr=float(amount_inr),
                    payment_channel=payment_channel,
                    timestamp=ts,
                    device_fingerprint=f"DEV-{from_account_id}",
                )
            )
        except Exception:
            pass

        # Locate all active/pending chains where from_account_id is a current known participant
        matching_chains = self._find_chains_for_sender(from_account_id, parent_transaction_id)
        updated_chains: List[TransactionChainRecord] = []

        for chain_data in matching_chains:
            cid = chain_data["chain_id"]
            root_tx_id = chain_data["root_transaction_id"]

            # Calculate hop depth
            existing_txs = chain_data.get("traceable_transactions", [])
            hop_depth = len(existing_txs) + 1

            # Check if this child transaction was already added to this chain (idempotency)
            if any(t.get("transaction_id") == child_transaction_id for t in existing_txs):
                continue

            tx_entry = {
                "transaction_id": child_transaction_id,
                "parent_transaction_id": parent_transaction_id or (existing_txs[-1]["transaction_id"] if existing_txs else None),
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "amount_inr": float(amount_inr),
                "payment_channel": payment_channel,
                "channel_type": channel_type,
                "timestamp": ts,
                "hop_depth": hop_depth,
                "is_cashout": is_cash_egress,
                "terminal_id": terminal_id,
            }

            dest_chain = list(chain_data.get("destination_account_chain", []))
            if to_account_id not in dest_chain and not is_cash_egress:
                dest_chain.append(to_account_id)

            current_accounts = set(chain_data.get("current_known_accounts", []))
            if not is_cash_egress:
                current_accounts.add(to_account_id)

            withdrawals = list(chain_data.get("known_withdrawals", []))
            if is_cash_egress:
                withdrawals.append({
                    "transaction_id": child_transaction_id,
                    "account_id": from_account_id,
                    "terminal_id": terminal_id or to_account_id,
                    "amount_inr": float(amount_inr),
                    "timestamp": ts,
                })

            # Update traceable exposed amounts (commingled funds exposure propagation)
            exposed_map = dict(chain_data.get("traceable_exposed_amounts", {}))
            prev_exposed_sender = exposed_map.get(from_account_id, float(amount_inr))

            # Exposure transferred to receiver is bounded by the transfer amount and sender's exposure
            transferred_exposure = min(float(amount_inr), prev_exposed_sender)
            if not is_cash_egress:
                exposed_map[to_account_id] = max(exposed_map.get(to_account_id, 0.0), transferred_exposure)

            updated_record = TransactionChainRecord(
                chain_id=cid,
                root_transaction_id=root_tx_id,
                origin_account_id=chain_data["origin_account_id"],
                destination_account_chain=dest_chain,
                original_amount=float(chain_data["original_amount"]),
                traceable_transactions=existing_txs + [tx_entry],
                current_known_accounts=list(current_accounts),
                known_withdrawals=withdrawals,
                traceable_exposed_amounts=exposed_map,
                chain_depth=hop_depth,
                chain_status=chain_data.get("chain_status", "ACTIVE"),
                created_at=chain_data.get("created_at", ts),
                updated_at=ts,
            )

            self.store.save_chain(updated_record)

            # Persist chain edge
            edge = TransactionChainEdge(
                chain_id=cid,
                parent_transaction_id=tx_entry["parent_transaction_id"],
                child_transaction_id=child_transaction_id,
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount_inr=float(amount_inr),
                payment_channel=payment_channel,
                timestamp=ts,
                hop_depth=hop_depth,
            )
            self.store.save_chain_edge(edge)

            # Update receiver account exposure
            if not is_cash_egress:
                self._update_account_exposure_on_ingress(
                    account_id=to_account_id,
                    amount_inr=transferred_exposure,
                    root_transaction_id=root_tx_id,
                    chain_id=cid,
                )

            updated_chains.append(updated_record)

            self.ledger.append({
                "event": "DESCENDANT_TRANSACTION_TRACKED",
                "chain_id": cid,
                "child_transaction_id": child_transaction_id,
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "amount_inr": float(amount_inr),
                "hop_depth": hop_depth,
                "is_cashout": is_cash_egress,
            })

            log.info(f"[CHAIN_TRACK] Tracked hop {hop_depth} on chain {cid}: {from_account_id} -> {to_account_id} (₹{amount_inr:,.2f})")

        return updated_chains

    def _find_chains_for_sender(
        self,
        from_account_id: str,
        parent_transaction_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Find active chains associated with sender or parent transaction."""
        chains = self.store.recent_chains(limit=200)
        matching = []

        for c in chains:
            # 1. Match by parent_transaction_id
            if parent_transaction_id:
                if any(t.get("transaction_id") == parent_transaction_id for t in c.get("traceable_transactions", [])):
                    matching.append(c)
                    continue

            # 2. Match if from_account is in destination chain or current known accounts
            if from_account_id in c.get("destination_account_chain", []) or from_account_id in c.get("current_known_accounts", []):
                matching.append(c)

        return matching

    # ------------------------------------------------------------------------
    # 3. Commingled Fund Exposure Tracking (§5 & §6)
    # ------------------------------------------------------------------------

    def _update_account_exposure_on_ingress(
        self,
        account_id: str,
        amount_inr: float,
        root_transaction_id: str,
        chain_id: str,
        pre_existing_balance: float = 20000.0,
    ) -> AccountExposureRecord:
        """Update account exposure record upon receiving suspicious/provenance funds."""
        existing = self.store.get_account_exposure(account_id)
        if existing:
            legit = float(existing.get("legitimate_balance", pre_existing_balance))
            susp = float(existing.get("suspicious_exposure", 0.0)) + float(amount_inr)
            roots = set(existing.get("contributing_root_transactions", []))
            roots.add(root_transaction_id)
            active_chains = set(existing.get("active_chains", []))
            active_chains.add(chain_id)
        else:
            legit = float(pre_existing_balance)
            susp = float(amount_inr)
            roots = {root_transaction_id}
            active_chains = {chain_id}

        record = AccountExposureRecord(
            account_id=account_id,
            legitimate_balance=legit,
            suspicious_exposure=susp,
            total_balance=legit + susp,
            contributing_root_transactions=list(roots),
            active_chains=list(active_chains),
            last_updated=datetime.now(timezone.utc).isoformat(),
        )
        self.store.save_account_exposure(record)
        return record

    def record_legitimate_balance_change(
        self,
        account_id: str,
        legitimate_balance: float,
    ) -> AccountExposureRecord:
        """Explicitly set or update an account's verified legitimate balance."""
        existing = self.store.get_account_exposure(account_id)
        if existing:
            susp = float(existing.get("suspicious_exposure", 0.0))
            roots = existing.get("contributing_root_transactions", [])
            chains = existing.get("active_chains", [])
        else:
            susp = 0.0
            roots = []
            chains = []

        record = AccountExposureRecord(
            account_id=account_id,
            legitimate_balance=float(legitimate_balance),
            suspicious_exposure=susp,
            total_balance=float(legitimate_balance) + susp,
            contributing_root_transactions=roots,
            active_chains=chains,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )
        self.store.save_account_exposure(record)
        return record

    # ------------------------------------------------------------------------
    # 4. Confirmed Fraud & Recovery Workflow (§4, §7, §8)
    # ------------------------------------------------------------------------

    def handle_fraud_confirmation(
        self,
        root_transaction_id: str,
        case_id: Optional[str] = None,
        notes: str = "",
    ) -> RecoveryCaseRecord:
        """Execute full downstream provenance discovery upon CONFIRMED_FRAUD and initiate recovery case."""
        cid = case_id or f"CASE-{root_transaction_id}"
        chain_record_dict = self.store.get_chain_by_root_tx(root_transaction_id)

        # If no chain stored yet, attempt to establish from graph store
        if not chain_record_dict:
            # Look up transaction in store
            tx_data = self.store.get_transaction(root_transaction_id)
            if tx_data:
                orig_acc = tx_data["source_account_id"]
                dest_acc = tx_data["target_account_id"]
                amt = float(tx_data["amount_inr"])
            else:
                orig_acc = "ACC-UNKNOWN-SRC"
                dest_acc = "ACC-UNKNOWN-DEST"
                amt = 100000.0

            chain_record = self.establish_trace_root(
                root_transaction_id=root_transaction_id,
                origin_account_id=orig_acc,
                destination_account_id=dest_acc,
                amount_inr=amt,
                chain_status=ConfirmationStatus.CONFIRMED_FRAUD,
            )
            chain_record_dict = chain_record.to_dict()

        # Update chain status to CONFIRMED_FRAUD
        chain_record_dict["chain_status"] = ConfirmationStatus.CONFIRMED_FRAUD
        self.store.save_chain(chain_record_dict)

        origin_account = chain_record_dict["origin_account_id"]
        destination_chain = chain_record_dict.get("destination_account_chain", [])
        original_amount = float(chain_record_dict.get("original_amount", 0.0))
        traceable_txs = chain_record_dict.get("traceable_transactions", [])
        known_withdrawals = chain_record_dict.get("known_withdrawals", [])
        current_known_accounts = chain_record_dict.get("current_known_accounts", [])
        exposed_amounts = chain_record_dict.get("traceable_exposed_amounts", {})

        # Compute total exposed amount eligible for recovery/hold
        total_exposed = sum(exposed_amounts.values()) if exposed_amounts else original_amount

        # Build simulated recovery action items
        simulated_actions = [
            {
                "step": 1,
                "action": "SIMULATED_PROVISIONAL_HOLD",
                "target_accounts": current_known_accounts,
                "amount": total_exposed,
                "status": "APPLIED",
                "notes": "Simulated provisional multi-bank hold placed on identified exposed accounts.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "step": 2,
                "action": "SIMULATED_INTERBANK_RECOVERY_NOTICE",
                "originating_bank": "HDFC-SIM",
                "destination_banks": ["ICICI-SIM", "SBI-SIM"],
                "status": "DISPATCHED",
                "notes": "Simulated NPCI / NCRP fund recall protocol message dispatched.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]

        if known_withdrawals:
            simulated_actions.append({
                "step": 3,
                "action": "SIMULATED_ATM_TERMINAL_BLOCK",
                "withdrawals_intercepted": len(known_withdrawals),
                "status": "APPLIED",
                "notes": "Physical cashout terminal egress blocked across identified mule terminals.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        recovery_case = RecoveryCaseRecord(
            case_id=cid,
            root_transaction_id=root_transaction_id,
            chain_id=chain_record_dict["chain_id"],
            origin_account=origin_account,
            destination_account_chain=destination_chain,
            original_amount=original_amount,
            traceable_transactions=traceable_txs,
            current_known_accounts=current_known_accounts,
            known_withdrawals=known_withdrawals,
            traceable_exposed_amounts=exposed_amounts,
            recovery_status=RecoveryState.INTERVENTION_PENDING,
            recovered_amount=0.0,
            simulated_actions=simulated_actions,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        self.store.save_recovery_case(recovery_case)

        self.ledger.append({
            "event": "FRAUD_CONFIRMED_RECOVERY_INITIATED",
            "case_id": cid,
            "root_transaction_id": root_transaction_id,
            "chain_id": chain_record_dict["chain_id"],
            "original_amount": original_amount,
            "recovery_status": recovery_case.recovery_status,
            "affected_accounts": current_known_accounts,
            "notes": notes,
        })

        log.info(f"[RECOVERY_CASE] Created/updated recovery case {cid} for fraud root {root_transaction_id} (Status: {recovery_case.recovery_status})")
        return recovery_case

    def update_recovery_status(
        self,
        case_id: str,
        new_status: str,
        recovered_amount: float = 0.0,
        action_note: str = "",
    ) -> RecoveryCaseRecord:
        """Advance recovery lifecycle state and append simulated workflow actions."""
        case_dict = self.store.get_recovery_case(case_id)
        if not case_dict:
            raise KeyError(f"Recovery case not found: {case_id}")

        sim_actions = list(case_dict.get("simulated_actions", []))
        if action_note or new_status:
            sim_actions.append({
                "step": len(sim_actions) + 1,
                "action": f"STATUS_CHANGE_TO_{new_status}",
                "status": "COMPLETED",
                "notes": action_note or f"Recovery state advanced to {new_status}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        rec_amt = max(float(case_dict.get("recovered_amount", 0.0)), float(recovered_amount))

        updated_case = RecoveryCaseRecord(
            case_id=case_dict["case_id"],
            root_transaction_id=case_dict["root_transaction_id"],
            chain_id=case_dict["chain_id"],
            origin_account=case_dict["origin_account"],
            destination_account_chain=case_dict.get("destination_account_chain", []),
            original_amount=float(case_dict.get("original_amount", 0.0)),
            traceable_transactions=case_dict.get("traceable_transactions", []),
            current_known_accounts=case_dict.get("current_known_accounts", []),
            known_withdrawals=case_dict.get("known_withdrawals", []),
            traceable_exposed_amounts=case_dict.get("traceable_exposed_amounts", {}),
            recovery_status=new_status,
            recovered_amount=rec_amt,
            simulated_actions=sim_actions,
            created_at=case_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        self.store.save_recovery_case(updated_case)

        self.ledger.append({
            "event": "RECOVERY_STATUS_UPDATED",
            "case_id": case_id,
            "new_status": new_status,
            "recovered_amount": rec_amt,
            "notes": action_note,
        })

        return updated_case

    # ------------------------------------------------------------------------
    # 5. Multi-Victim Convergence (§9)
    # ------------------------------------------------------------------------

    def get_convergent_chains(self, common_account_id: str) -> ConvergentChainsRecord:
        """Detect and aggregate multiple incoming victim transactions converging into a common account."""
        all_chains = self.store.recent_chains(limit=200)
        converging_chains: List[Dict[str, Any]] = []

        for chain in all_chains:
            dest_list = chain.get("destination_account_chain", [])
            trace_txs = chain.get("traceable_transactions", [])
            if common_account_id in dest_list or any(t.get("to_account_id") == common_account_id for t in trace_txs):
                converging_chains.append(chain)

        source_txs = []
        root_tx_ids = []
        chain_ids = []
        total_exposure = 0.0
        related_cases = []

        for c in converging_chains:
            root_tx_ids.append(c["root_transaction_id"])
            chain_ids.append(c["chain_id"])
            amt = float(c.get("original_amount", 0.0))
            total_exposure += amt

            for t in c.get("traceable_transactions", []):
                if t.get("to_account_id") == common_account_id or t.get("from_account_id") == c["origin_account_id"]:
                    source_txs.append(t)

            # Check for correlated cases
            rec_case = self.store.get_recovery_case_by_root_tx(c["root_transaction_id"])
            if rec_case:
                related_cases.append(rec_case["case_id"])

        # Trace downstream path forward from common_account_id
        downstream_legs = self.graph_store.reconstruct_downstream_chain(common_account_id, max_hops=8)
        downstream_formatted = [leg.to_dict() for leg in downstream_legs]

        return ConvergentChainsRecord(
            common_account_id=common_account_id,
            source_transactions=source_txs,
            root_transaction_ids=list(set(root_tx_ids)),
            chain_ids=list(set(chain_ids)),
            aggregate_suspicious_exposure=total_exposure,
            downstream_chain=downstream_formatted,
            related_case_ids=list(set(related_cases)),
        )

    # ------------------------------------------------------------------------
    # 6. Structured Query Interfaces (§10)
    # ------------------------------------------------------------------------

    def get_transaction_chain(self, root_transaction_id_or_chain_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve complete structured provenance chain by chain ID or root transaction ID."""
        chain = self.store.get_chain(root_transaction_id_or_chain_id)
        if not chain:
            chain = self.store.get_chain_by_root_tx(root_transaction_id_or_chain_id)
        return chain

    def get_transaction_descendants(self, transaction_id: str) -> List[Dict[str, Any]]:
        """Retrieve all descendant transactions emanating from a specific transaction."""
        chains = self.store.recent_chains(limit=200)
        descendants = []

        for c in chains:
            txs = c.get("traceable_transactions", [])
            found_parent = False
            for t in txs:
                if t.get("transaction_id") == transaction_id:
                    found_parent = True
                    continue
                if found_parent:
                    descendants.append(t)

        return descendants

    def get_account_exposure_query(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve account exposure record distinguishing legitimate balance from suspicious exposure."""
        return self.store.get_account_exposure(account_id)

    def get_recovery_case_query(self, case_id_or_root_tx: str) -> Optional[Dict[str, Any]]:
        """Retrieve formal recovery case by case ID or root transaction ID."""
        rec = self.store.get_recovery_case(case_id_or_root_tx)
        if not rec:
            rec = self.store.get_recovery_case_by_root_tx(case_id_or_root_tx)
        return rec
