"""pipeline/graph_store.py

In-memory directed transaction graph (NetworkX) supporting:
1. Real-time streaming sliding-window ingestion with application-level idempotence and memory bounding.
2. Complete graph query interfaces for the 8 explainable heuristic detection rules.
3. Account and terminal static metadata indexing.
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Union

import math
import networkx as nx

from shared.schemas import AccountNodeMetadata, MoneyTrailLeg, TransactionEvent, ValidationError

log = logging.getLogger("graph_store")


def utcnow() -> datetime:
    """Current time as an aware UTC datetime (single source for all rules)."""
    return datetime.now(timezone.utc)


def _as_utc(dt: Union[str, datetime]) -> datetime:
    """Convert datetime or ISO string to UTC aware datetime."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if isinstance(dt, str):
        clean_ts = dt.replace("Z", "+00:00")
        try:
            d = datetime.fromisoformat(clean_ts)
            if d.tzinfo is None:
                return d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except Exception:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f"):
                try:
                    d = datetime.strptime(dt.replace("Z", ""), fmt)
                    return d.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            raise ValueError(f"Unrecognized timestamp format: '{dt}'")
    raise ValueError(f"Expected datetime or str, got: {type(dt)}")


def _parse_ts(ts: Union[str, datetime]) -> datetime:
    """Alias for UTC parsing."""
    return _as_utc(ts)


class GraphStore:
    """Directed graph representing accounts (nodes) and transactions (edges)."""

    def __init__(self, fan_window_seconds: int = 300) -> None:
        """
        fan_window_seconds: sliding window used for fan-in/fan-out counting
        (default 5 minutes — matches the rapid-layering pattern).
        """
        self.graph = nx.MultiDiGraph()
        self.fan_window = timedelta(seconds=fan_window_seconds)

        # account_id -> deque of (timestamp, counterparty_id, direction) for windowed queries
        self._recent_activity = defaultdict(deque)

        # reference data
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.terminals: Dict[str, Dict[str, Any]] = {}
        self._metadata: Dict[str, AccountNodeMetadata] = {}

        # device fingerprint index
        self._device_senders = defaultdict(set)
        self._account_devices = defaultdict(set)

        # transaction deduplication & history
        self._seen_tx_ids: Set[str] = set()
        self._seen_tx_order: deque = deque()
        self._txns: Dict[str, TransactionEvent] = {}

        # ADDITIVE (Phase 2): shared-KYC-identity index for identity_cluster_rule
        # (many accounts opened under one stolen/purchased identity).
        self._kyc_accounts: Dict[str, Set[str]] = defaultdict(set)

        # ADDITIVE (Phase 2): live terminal-usage timeline for geo_velocity_rule
        # (physically-impossible-travel between two cash-out locations). This is
        # DELIBERATELY separate from the locked 7-field transaction schema/topic
        # (Architecture.md §6.1) — it is fed from a distinct "terminal_usage"
        # stream/table, never from TransactionEvent itself.
        self._terminal_usage: Dict[str, deque] = defaultdict(deque)
        self._terminal_usage_maxlen = 20

    # ------------------------------------------------------------------------
    # Reference Data Loading
    # ------------------------------------------------------------------------

    def add_account_metadata(self, meta: AccountNodeMetadata) -> None:
        """Attach static account attributes (first-seen metadata)."""
        self._metadata[meta.account_id] = meta
        self.accounts[meta.account_id] = meta.to_dict()
        if not self.graph.has_node(meta.account_id):
            self.graph.add_node(meta.account_id, node_type="account", meta=meta, **meta.to_dict())
        else:
            self.graph.nodes[meta.account_id]["meta"] = meta
            for k, v in meta.to_dict().items():
                self.graph.nodes[meta.account_id][k] = v

        if getattr(meta, "kyc_identity_id", None):
            self._kyc_accounts[meta.kyc_identity_id].add(meta.account_id)

    def load_accounts(self, accounts: List[Dict[str, Any]]) -> None:
        """Bulk load account reference data."""
        for acc in accounts:
            meta = AccountNodeMetadata.from_dict(acc) if not isinstance(acc, AccountNodeMetadata) else acc
            self.add_account_metadata(meta)

    def load_terminals(self, terminals: List[Dict[str, Any]]) -> None:
        """Bulk load terminal reference data."""
        for term in terminals:
            tid = str(term.get("terminal_id", ""))
            self.terminals[tid] = term
            if not self.graph.has_node(tid):
                self.graph.add_node(tid, node_type="terminal", **term)

    # ------------------------------------------------------------------------
    # Live Streaming Transaction Ingestion
    # ------------------------------------------------------------------------

    def add_transaction(self, tx: Union[Dict[str, Any], TransactionEvent]) -> bool:
        """
        Add a transaction to the graph.

        Supports both dict payloads (matching 7 locked fields) and TransactionEvent objects.
        Returns True if accepted, False if duplicate (idempotent).
        """
        if isinstance(tx, dict):
            tx_id = tx.get("transaction_id")
            if not tx_id:
                raise KeyError("transaction_id")
            if tx_id in self._seen_tx_ids or tx_id in self._txns:
                return False

            event = TransactionEvent.from_dict(tx)
        elif isinstance(tx, TransactionEvent):
            tx_id = tx.transaction_id
            if tx_id in self._seen_tx_ids or tx_id in self._txns:
                return False
            event = tx
        else:
            raise TypeError(f"Expected dict or TransactionEvent, got: {type(tx)}")

        src, tgt = event.source_account_id, event.target_account_id
        ts = event.timestamp_utc
        dev = event.device_fingerprint

        self._seen_tx_ids.add(tx_id)
        self._seen_tx_order.append((ts, tx_id))
        self._txns[tx_id] = event
        self._prune_seen_tx(ts)

        for node in (src, tgt):
            if not self.graph.has_node(node):
                self.graph.add_node(node, node_type="account")

        self.graph.add_edge(
            src, tgt,
            transaction_id=tx_id,
            amount_inr=event.amount_inr,
            amount=event.amount_inr,
            timestamp=ts,
            payment_channel=event.payment_channel,
            channel=event.payment_channel,
            device_fingerprint=dev,
            device=dev,
            txn=event,
        )

        if dev:
            self._device_senders[dev].add(src)
            self._account_devices[src].add(dev)

        self._recent_activity[src].append((ts, tgt, "out"))
        self._recent_activity[tgt].append((ts, src, "in"))
        self._prune(src, ts)
        self._prune(tgt, ts)
        return True

    def _prune_seen_tx(self, now: datetime):
        """Prune old seen transaction IDs to bound memory footprint."""
        retention = self.fan_window * 2
        self._seen_tx_order = deque(
            (ts, tid) for ts, tid in self._seen_tx_order if timedelta(0) <= (now - ts) <= retention
        )
        self._seen_tx_ids = {tid for _, tid in self._seen_tx_order}

    def _prune(self, account_id: str, now: datetime):
        """Prune activity deque outside sliding window."""
        dq = self._recent_activity[account_id]
        self._recent_activity[account_id] = deque(
            entry for entry in dq if timedelta(0) <= (now - entry[0]) <= self.fan_window
        )

    # ------------------------------------------------------------------------
    # Reads / Queries used by Detection Rules & Pipeline
    # ------------------------------------------------------------------------

    def has_account(self, account_id: str) -> bool:
        """True if the account exists in the graph."""
        return account_id in self.graph

    def get_account_metadata(self, account_id: str) -> Optional[AccountNodeMetadata]:
        """Return static metadata for an account, or None if unknown."""
        return self._metadata.get(account_id)

    def transactions_involving(
        self,
        account_id: str,
        window_seconds: Optional[int] = None,
        direction: str = "both",
        as_of: Optional[datetime] = None,
    ) -> List[TransactionEvent]:
        """Incoming ('in'), outgoing ('out') or all transaction events touching the account."""
        if not self.has_account(account_id):
            return []

        as_of_dt = _as_utc(as_of) if as_of is not None else utcnow()
        cutoff = as_of_dt - timedelta(seconds=window_seconds) if window_seconds else None
        result: List[TransactionEvent] = []

        if direction in ("both", "out"):
            for _s, _t, _k, data in self.graph.out_edges(account_id, keys=True, data=True):
                ts = data["timestamp"]
                if ts <= as_of_dt and (cutoff is None or ts >= cutoff):
                    result.append(data["txn"])

        if direction in ("both", "in"):
            for _s, _t, _k, data in self.graph.in_edges(account_id, keys=True, data=True):
                ts = data["timestamp"]
                if ts <= as_of_dt and (cutoff is None or ts >= cutoff):
                    result.append(data["txn"])

        return result

    def unique_incoming_sources(
        self,
        account_id: str,
        window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> Set[str]:
        """Distinct source accounts that paid INTO this account in the window."""
        return {e.source_account_id for e in self.transactions_involving(account_id, window_seconds, "in", as_of)}

    def unique_outgoing_targets(
        self,
        account_id: str,
        window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> Set[str]:
        """Distinct target accounts this account paid INTO in the window."""
        return {e.target_account_id for e in self.transactions_involving(account_id, window_seconds, "out", as_of)}

    def fan_in_count(
        self,
        account_id: str,
        window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> int:
        """Number of distinct accounts sending money to this account (fan-in)."""
        if window_seconds is not None or as_of is not None:
            return len(self.unique_incoming_sources(account_id, window_seconds, as_of))
        return sum(1 for _, _, d in self._recent_activity[account_id] if d == "in")

    def fan_out_count(
        self,
        account_id: str,
        window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> int:
        """Number of distinct accounts this account sent money to (fan-out)."""
        if window_seconds is not None or as_of is not None:
            return len(self.unique_outgoing_targets(account_id, window_seconds, as_of))
        return sum(1 for _, _, d in self._recent_activity[account_id] if d == "out")

    def distinct_counterparties_in_window(self, account_id: str) -> Set[str]:
        """Return set of all distinct counterparties in active window."""
        return {cp for _, cp, _ in self._recent_activity[account_id]}

    def get_neighborhood(
        self,
        account_id: str,
        degrees: int = 1,
        window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> Set[str]:
        """All accounts within `degrees` hops (BFS) of the account."""
        if not self.has_account(account_id):
            return set()

        seen: Set[str] = set()
        frontier = deque([(account_id, 0)])

        while frontier:
            node, depth = frontier.popleft()
            if depth >= degrees:
                continue
            nbrs = set(self.graph.successors(node)) | set(self.graph.predecessors(node))
            for nbr in nbrs:
                if nbr not in seen and nbr != account_id:
                    seen.add(nbr)
                    frontier.append((nbr, depth + 1))
        return seen

    def shares_device_fingerprint(self, account_id: str) -> List[str]:
        """
        Return other accounts that have also sent transactions using any
        device fingerprint used by account_id for outgoing transactions.
        """
        devices = self._account_devices.get(account_id, set())
        if not devices:
            return []
        other_accounts = set()
        for dev in devices:
            other_accounts.update(self._device_senders.get(dev, set()))
        other_accounts.discard(account_id)
        return sorted(list(other_accounts))

    def accounts_sharing_device_fingerprint(self, account_id: str) -> Set[str]:
        """Other accounts connected to the same device_fingerprint via any edge (in or out)."""
        if not self.has_account(account_id):
            return set()
        devs = set()
        for _, _, data in self.graph.out_edges(account_id, data=True):
            dev = data.get("device_fingerprint") or data.get("device")
            if dev:
                devs.add(dev)
        for _, _, data in self.graph.in_edges(account_id, data=True):
            dev = data.get("device_fingerprint") or data.get("device")
            if dev:
                devs.add(dev)
        if not devs:
            return set()
        sharers: Set[str] = set()
        for dev in devs:
            sharers.update(self._device_senders.get(dev, set()))
        sharers.discard(account_id)
        return sharers

    def historical_terminal_affinity(self, account_id: str) -> List[str]:
        """Terminals this account has historically cashed out at."""
        acc = self.accounts.get(account_id, {})
        if "historical_terminal_ids" in acc:
            return list(acc["historical_terminal_ids"])
        meta = self._metadata.get(account_id)
        return list(meta.historical_terminal_ids) if meta else []

    def historical_terminal_ids(self, account_id: str) -> List[str]:
        """Alias for historical_terminal_affinity."""
        return self.historical_terminal_affinity(account_id)

    def account_chain_depth(self, account_id: str, max_depth: int = 3) -> int:
        """
        Computes longest directed incoming path length within the sliding window,
        bounded to max_depth (0=source/isolated, 1=1-hop, 2=2-hop, 3=3+ hops).
        """
        visited = set()

        def _traverse_back(node: str, depth: int) -> int:
            if depth >= max_depth:
                return max_depth
            preds = {cp for _, cp, direction in self._recent_activity.get(node, []) if direction == "in"}
            unvisited_preds = preds - visited
            if not unvisited_preds:
                return depth
            visited.update(unvisited_preds)
            return max(_traverse_back(p, depth + 1) for p in unvisited_preds)

        return _traverse_back(account_id, 0)

    def trail_depth(
        self,
        account_id: str,
        window_seconds: Optional[int] = None,
        max_depth: int = 8,
        as_of: Optional[datetime] = None,
    ) -> int:
        """Longest reverse chain of distinct accounts flowing INTO this account."""
        if not self.has_account(account_id):
            return 0

        as_of_dt = _as_utc(as_of) if as_of is not None else utcnow()
        cutoff = as_of_dt - timedelta(seconds=window_seconds) if window_seconds else None
        visited: Set[str] = {account_id}
        frontier = deque([(account_id, 0)])
        max_d = 0

        while frontier:
            node, depth = frontier.popleft()
            if depth >= max_depth:
                continue
            for src, _dst, _k, data in self.graph.in_edges(node, keys=True, data=True):
                ts = data["timestamp"]
                if ts > as_of_dt or (cutoff is not None and ts < cutoff):
                    continue
                if src not in visited:
                    visited.add(src)
                    nd = depth + 1
                    max_d = max(max_d, nd)
                    frontier.append((src, nd))
        return max_d

    def edge_latency_between(self, account_id: str, direction: str = "out") -> Optional[timedelta]:
        """Smallest time gap between a relevant inbound and the given outbound edge."""
        if not self.has_account(account_id):
            return None

        in_times = sorted(
            e.timestamp_utc for e in self.transactions_involving(account_id, direction="in")
        )
        if not in_times:
            return None

        import bisect
        edges = (
            self.graph.out_edges(account_id, data=True)
            if direction == "out"
            else self.graph.in_edges(account_id, data=True)
        )
        best = None
        for _s, _t, data in edges:
            ts = data["timestamp"]
            idx = bisect.bisect_right(in_times, ts)
            if idx > 0:
                gap = ts - in_times[idx - 1]
                if best is None or gap < best:
                    best = gap
        return best

    def forwarded_transactions(
        self,
        account_id: str,
        window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> List[TransactionEvent]:
        """Outgoing transactions that have at least one prior inbound edge to the account."""
        if not self.has_account(account_id):
            return []

        as_of_dt = _as_utc(as_of) if as_of is not None else utcnow()
        cutoff = as_of_dt - timedelta(seconds=window_seconds) if window_seconds else None
        in_times = [
            t.timestamp_utc
            for t in self.transactions_involving(account_id, window_seconds=window_seconds, direction="in", as_of=as_of)
        ]
        if not in_times:
            return []

        out_events = []
        for _s, _t, data in self.graph.out_edges(account_id, data=True):
            ev = data["txn"]
            if ev.timestamp_utc > as_of_dt or (cutoff is not None and ev.timestamp_utc < cutoff):
                continue
            if any(t <= ev.timestamp_utc for t in in_times):
                out_events.append(ev)
        return out_events

    # ------------------------------------------------------------------------
    # ADDITIVE (Phase 2): KYC identity clustering — mule-ring detection.
    # ------------------------------------------------------------------------

    def accounts_sharing_kyc_identity(self, account_id: str) -> Set[str]:
        """Other accounts registered under the same KYC identifier (PAN/phone/
        address hash) as `account_id` — the "one person, many mule accounts"
        signal. Independent of device_fingerprint sharing."""
        meta = self._metadata.get(account_id)
        kyc = getattr(meta, "kyc_identity_id", None) if meta else None
        if not kyc:
            return set()
        sharers = set(self._kyc_accounts.get(kyc, set()))
        sharers.discard(account_id)
        return sharers

    # ------------------------------------------------------------------------
    # ADDITIVE (Phase 2): live terminal-usage timeline — geo-velocity /
    # impossible-travel detection. Fed from a separate "terminal_usage" stream,
    # NOT from the locked TransactionEvent schema/topic.
    # ------------------------------------------------------------------------

    def record_terminal_usage(
        self,
        account_id: str,
        terminal_id: str,
        timestamp: Union[str, datetime],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> None:
        """Log one physical cash-out/card-present event for an account."""
        ts = _as_utc(timestamp)
        if latitude is None or longitude is None:
            term = self.terminals.get(str(terminal_id), {})
            latitude = latitude if latitude is not None else term.get("latitude")
            longitude = longitude if longitude is not None else term.get("longitude")
        dq = self._terminal_usage[account_id]
        dq.append({
            "terminal_id": str(terminal_id),
            "timestamp": ts,
            "latitude": latitude,
            "longitude": longitude,
        })
        while len(dq) > self._terminal_usage_maxlen:
            dq.popleft()
        # keep chronological order even if events arrive slightly out of order
        self._terminal_usage[account_id] = deque(sorted(dq, key=lambda e: e["timestamp"]))

    def recent_terminal_usages(self, account_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Most recent `limit` terminal-usage events for the account, oldest first."""
        dq = self._terminal_usage.get(account_id)
        if not dq:
            return []
        return list(dq)[-limit:]

    # ------------------------------------------------------------------------
    # ADDITIVE (SIH26184): Detailed Money Trail, Selective Funds, Spatial Context
    # ------------------------------------------------------------------------

    def reconstruct_detailed_chain(
        self,
        account_id: str,
        max_hops: int = 8,
        as_of: Optional[datetime] = None,
    ) -> List[MoneyTrailLeg]:
        """Reconstruct detailed chronological money trail walking backward from aggregator/flagged node."""
        if not self.has_account(account_id):
            return []

        legs: List[MoneyTrailLeg] = []
        cur = account_id
        visited: Set[str] = {cur}

        for hop in range(1, max_hops + 1):
            incoming = self.transactions_involving(cur, direction="in", as_of=as_of)
            if not incoming:
                break
            # Pick largest incoming transaction leg
            leg_tx = max(incoming, key=lambda e: e.amount_inr)
            src = leg_tx.source_account_id
            if src in visited:
                break
            visited.add(src)

            src_meta = self.get_account_metadata(src)
            tgt_meta = self.get_account_metadata(cur)
            src_tier = src_meta.account_tier if src_meta else "victim"
            tgt_tier = tgt_meta.account_tier if tgt_meta else "mule"

            flags: List[str] = []
            if getattr(src_meta, "kyc_identity_id", None) and getattr(tgt_meta, "kyc_identity_id", None):
                if src_meta.kyc_identity_id == tgt_meta.kyc_identity_id:
                    flags.append("Shared KYC Identity Cluster")
            if leg_tx.device_fingerprint:
                sharers = self.shares_device_fingerprint(cur)
                if src in sharers:
                    flags.append("Shared Device Fingerprint")

            legs.append(
                MoneyTrailLeg(
                    hop_index=hop,
                    source_account_id=src,
                    target_account_id=cur,
                    amount_inr=float(leg_tx.amount_inr),
                    timestamp=_as_utc(leg_tx.timestamp).isoformat(),
                    payment_channel=leg_tx.payment_channel,
                    direction="in",
                    source_tier=src_tier,
                    target_tier=tgt_tier,
                    suspicious_flags=flags,
                )
            )
            cur = src

        # Reverse so victim/origin is hop 1, progressing to aggregator
        reversed_legs = list(reversed(legs))
        for i, leg in enumerate(reversed_legs):
            leg.hop_index = i + 1
        return reversed_legs

    def reconstruct_downstream_chain(
        self,
        start_account_id: str,
        since_timestamp: Optional[Union[str, datetime]] = None,
        max_hops: int = 8,
        as_of: Optional[datetime] = None,
    ) -> List[MoneyTrailLeg]:
        """Reconstruct chronological downstream money trail walking forward from originating/victim node."""
        if not self.has_account(start_account_id):
            return []

        since_dt = _as_utc(since_timestamp) if since_timestamp is not None else None
        legs: List[MoneyTrailLeg] = []
        cur = start_account_id
        visited: Set[str] = {cur}

        for hop in range(1, max_hops + 1):
            outgoing = self.transactions_involving(cur, direction="out", as_of=as_of)
            if since_dt:
                outgoing = [tx for tx in outgoing if tx.timestamp_utc >= since_dt]
            if not outgoing:
                break

            # Pick largest forward transaction leg
            leg_tx = max(outgoing, key=lambda e: e.amount_inr)
            tgt = leg_tx.target_account_id
            if tgt in visited:
                break
            visited.add(tgt)

            src_meta = self.get_account_metadata(cur)
            tgt_meta = self.get_account_metadata(tgt)
            src_tier = src_meta.account_tier if src_meta else "mule"
            tgt_tier = tgt_meta.account_tier if tgt_meta else "mule"

            flags: List[str] = []
            if getattr(src_meta, "kyc_identity_id", None) and getattr(tgt_meta, "kyc_identity_id", None):
                if src_meta.kyc_identity_id == tgt_meta.kyc_identity_id:
                    flags.append("Shared KYC Identity Cluster")
            if leg_tx.device_fingerprint:
                sharers = self.shares_device_fingerprint(cur)
                if tgt in sharers:
                    flags.append("Shared Device Fingerprint")

            legs.append(
                MoneyTrailLeg(
                    hop_index=hop,
                    source_account_id=cur,
                    target_account_id=tgt,
                    amount_inr=float(leg_tx.amount_inr),
                    timestamp=_as_utc(leg_tx.timestamp).isoformat(),
                    payment_channel=leg_tx.payment_channel,
                    direction="out",
                    source_tier=src_tier,
                    target_tier=tgt_tier,
                    suspicious_flags=flags,
                )
            )
            cur = tgt
            since_dt = leg_tx.timestamp_utc

        return legs

    def get_downstream_transactions_from(
        self,
        start_account_id: str,
        since_timestamp: Optional[Union[str, datetime]] = None,
        as_of: Optional[datetime] = None,
    ) -> List[TransactionEvent]:
        """Fetch all chronological downstream transactions starting from an account."""
        legs = self.reconstruct_downstream_chain(start_account_id, since_timestamp=since_timestamp, as_of=as_of)
        tx_list: List[TransactionEvent] = []
        for leg in legs:
            for tx in self.transactions_involving(leg.source_account_id, direction="out", as_of=as_of):
                if tx.target_account_id == leg.target_account_id:
                    tx_list.append(tx)
                    break
        return tx_list

    def compute_account_funds(
        self,
        account_id: str,
        window_seconds: int = 3600,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Compute selective fund breakdown: existing older funds vs recent suspicious received funds vs forward amount."""
        as_of_dt = _as_utc(as_of) if as_of is not None else utcnow()
        cutoff = as_of_dt - timedelta(seconds=window_seconds)

        all_in = self.transactions_involving(account_id, direction="in")
        recent_in = [tx for tx in all_in if tx.timestamp_utc >= cutoff]
        older_in = [tx for tx in all_in if tx.timestamp_utc < cutoff]

        all_out = self.transactions_involving(account_id, direction="out")
        older_out = [tx for tx in all_out if tx.timestamp_utc < cutoff]
        recent_out = [tx for tx in all_out if tx.timestamp_utc >= cutoff]

        older_in_amt = sum(tx.amount_inr for tx in older_in)
        older_out_amt = sum(tx.amount_inr for tx in older_out)
        existing_balance = max(0.0, older_in_amt - older_out_amt)

        # Baseline demo fallback for accounts with no older transaction history
        if existing_balance == 0.0:
            existing_balance = 20000.0

        suspicious_amount = sum(tx.amount_inr for tx in recent_in) if recent_in else (
            sum(tx.amount_inr for tx in all_in) if all_in else 100000.0
        )
        onward_moved = sum(tx.amount_inr for tx in recent_out)

        # Protected amount is targeted to the recent suspicious amount
        protected_amount = suspicious_amount

        return {
            "existing_balance": round(existing_balance, 2),
            "suspicious_amount": round(suspicious_amount, 2),
            "protected_amount": round(protected_amount, 2),
            "onward_moved_amount": round(onward_moved, 2),
        }

    def find_nearby_terminals(
        self,
        terminal_id: str,
        radius_km: float = 5.0,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find other terminals within radius_km using Haversine distance."""
        base = self.terminals.get(str(terminal_id))
        if not base or "latitude" not in base or "longitude" not in base:
            return []

        b_lat, b_lon = float(base["latitude"]), float(base["longitude"])
        results = []

        for tid, term in self.terminals.items():
            if tid == terminal_id:
                continue
            lat = term.get("latitude")
            lon = term.get("longitude")
            if lat is None or lon is None:
                continue

            dlat = math.radians(float(lat) - b_lat)
            dlon = math.radians(float(lon) - b_lon)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(b_lat)) * math.cos(math.radians(float(lat))) * math.sin(dlon / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            dist = 6371.0 * c

            if dist <= radius_km:
                results.append({
                    "terminal_id": tid,
                    "terminal_type": term.get("terminal_type", "ATM_KIOSK"),
                    "district": term.get("district", ""),
                    "district_pincode": term.get("district_pincode", term.get("pincode", "")),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "distance_km": round(dist, 2),
                })

        results.sort(key=lambda x: x["distance_km"])
        return results[:limit]

    def record_account_terminal_activity(
        self,
        account_id: str,
        terminal_id: str,
        timestamp: Union[str, datetime],
    ) -> Dict[str, Any]:
        """Record recurring account-terminal cash-out attempts and calculate escalation tier."""
        self.record_terminal_usage(account_id, terminal_id, timestamp)
        usages = self.recent_terminal_usages(account_id, limit=20)
        matching = [u for u in usages if u["terminal_id"] == str(terminal_id)]
        count = len(matching)

        if count >= 3:
            escalation_state = "PERSISTENT_TERMINAL_RISK"
            risk_multiplier = 1.5
            action = "ESCALATE_TERMINAL_BLOCK"
        elif count == 2:
            escalation_state = "ELEVATED_RISK"
            risk_multiplier = 1.25
            action = "ELEVATE_MONITORING"
        else:
            escalation_state = "MONITORED"
            risk_multiplier = 1.0
            action = "INITIAL_MONITOR"

        return {
            "account_id": account_id,
            "terminal_id": terminal_id,
            "occurrence_count": count,
            "escalation_state": escalation_state,
            "risk_multiplier": risk_multiplier,
            "recommended_action": action,
        }

