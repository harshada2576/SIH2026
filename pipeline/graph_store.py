"""In-memory networkx graph of accounts + transactions.

NOTE (Workstream 2 ownership): this is the graph API the detection rules read.
It is implemented here as a minimal stand-in so the scorer is independently
testable (Rules.md section 7: "a mocked stand-in is completely fine as a
short-term unblock"). Workstream 2 owns/evolves this file for the Kafka live
path. The public method names below are the ones the rules are written against.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Set

import networkx as nx

from shared.schemas import AccountNodeMetadata, TransactionEvent


def utcnow() -> datetime:
    """Current time as an aware UTC datetime (single source for all rules)."""
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Assume UTC for naive datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class GraphStore:
    """Directed graph: nodes are accounts, edges are transactions."""

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()
        self._metadata: Dict[str, AccountNodeMetadata] = {}
        self._txns: Dict[str, TransactionEvent] = {}

    # ---- writes -----------------------------------------------------------
    def add_transaction(self, event: TransactionEvent) -> None:
        """Add a directed edge from source to target carrying the event data."""
        if event.transaction_id in self._txns:
            raise ValueError(f"duplicate transaction_id: {event.transaction_id}")
        self._g.add_edge(
            event.source_account_id,
            event.target_account_id,
            timestamp=_as_utc(event.timestamp),
            amount=event.amount_inr,
            channel=event.payment_channel,
            device=event.device_fingerprint,
            txn=event,
        )
        self._txns[event.transaction_id] = event

    def add_account_metadata(self, meta: AccountNodeMetadata) -> None:
        """Attach static account attributes (first-seen metadata)."""
        self._metadata[meta.account_id] = meta
        self._g.add_node(meta.account_id, meta=meta)

    # ---- reads used by the rules ------------------------------------------
    def get_account_metadata(self, account_id: str) -> Optional[AccountNodeMetadata]:
        """Return static metadata for an account, or None if unknown."""
        return self._metadata.get(account_id)

    def has_account(self, account_id: str) -> bool:
        """True if the account has been seen as a node."""
        return account_id in self._g

    def transactions_involving(
        self,
        account_id: str,
        window_seconds: Optional[int] = None,
        direction: str = "both",
        as_of: Optional[datetime] = None,
    ) -> List[TransactionEvent]:
        """Incoming ('in'), outgoing ('out') or all edges touching the account.

        When window_seconds is set, only edges at or after as_of - window are returned.
        """
        if not self.has_account(account_id):
            return []
        as_of = _as_utc(as_of) if as_of is not None else utcnow()
        cutoff = as_of - timedelta(seconds=window_seconds) if window_seconds else None
        result: List[TransactionEvent] = []
        for src, dst, data in self._g.edges(account_id, data=True):
            on_edge = (direction == "both" or direction == "out")
            if on_edge and (cutoff is None or data["timestamp"] >= cutoff):
                result.append(data["txn"])
        for src, dst, data in self._g.in_edges(account_id, data=True):
            on_edge = (direction == "both" or direction == "in")
            if on_edge and (cutoff is None or data["timestamp"] >= cutoff):
                result.append(data["txn"])
        return result

    def unique_incoming_sources(
        self, account_id: str, window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> Set[str]:
        """Distinct source accounts that paid INTO this account in the window."""
        return {e.source_account_id for e in self.transactions_involving(
            account_id, window_seconds, "in", as_of)}

    def unique_outgoing_targets(
        self, account_id: str, window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> Set[str]:
        """Distinct target accounts this account paid INTO in the window."""
        return {e.target_account_id for e in self.transactions_involving(
            account_id, window_seconds, "out", as_of)}

    def fan_in_count(
        self, account_id: str, window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> int:
        """Number of distinct accounts sending money to this account (fan-in)."""
        return len(self.unique_incoming_sources(account_id, window_seconds, as_of))

    def fan_out_count(
        self, account_id: str, window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> int:
        """Number of distinct accounts this account sent money to (fan-out)."""
        return len(self.unique_outgoing_targets(account_id, window_seconds, as_of))

    def get_neighborhood(
        self, account_id: str, degrees: int = 1,
        window_seconds: Optional[int] = None, as_of: Optional[datetime] = None,
    ) -> Set[str]:
        """All accounts within `degrees` hops (BFS) of the account, in the window."""
        if not self.has_account(account_id):
            return set()
        seen: Set[str] = set()
        frontier = deque([(account_id, 0)])
        while frontier:
            node, depth = frontier.popleft()
            for nbr in set(self._g.successors(node)) | set(self._g.predecessors(node)):
                if nbr not in seen and depth + 1 <= degrees:
                    seen.add(nbr)
                    frontier.append((nbr, depth + 1))
        return seen

    def accounts_sharing_device_fingerprint(self, account_id: str) -> Set[str]:
        """Other accounts connected to the same device_fingerprint via any edge."""
        if not self.has_account(account_id):
            return set()
        devs = {d["device"] for _, _, d in self._g.edges(account_id, data=True)}
        devs |= {d["device"] for _, _, d in self._g.in_edges(account_id, data=True)}
        sharers: Set[str] = set()
        for src, dst, d in self._g.edges(data=True):
            if d["device"] in devs:
                for a in (src, dst):
                    if a != account_id:
                        sharers.add(a)
        return sharers

    def trail_depth(
        self, account_id: str, window_seconds: Optional[int] = None,
        max_depth: int = 8, as_of: Optional[datetime] = None,
    ) -> int:
        """Longest reverse chain of distinct accounts flowing INTO this account.

        Depth 0 = no incoming trail, 1 = direct funders only, N = layered path.
        """
        if not self.has_account(account_id):
            return 0
        as_of = _as_utc(as_of) if as_of is not None else utcnow()
        cutoff = as_of - timedelta(seconds=window_seconds) if window_seconds else None
        visited: Dict[str, int] = {account_id: 0}
        frontier = deque([account_id])
        max_d = 0
        while frontier:
            node = frontier.popleft()
            for src, _dst, data in self._g.in_edges(node, data=True):
                if cutoff is not None and data["timestamp"] < cutoff:
                    continue
                nd = visited[node] + 1
                if nd <= max_depth and (src not in visited or visited[src] < nd):
                    visited[src] = max(visited.get(src, 0), nd)
                    max_d = max(max_d, nd)
                    frontier.append(src)
        return max_d

    def historical_terminal_ids(self, account_id: str) -> List[str]:
        """Terminals this account has historically cashed out at."""
        meta = self._metadata.get(account_id)
        return list(meta.historical_terminal_ids) if meta else []

    def edge_latency_between(self, account_id: str, direction: str = "out") -> Optional[timedelta]:
        """Smallest time gap between a relevant inbound and the given outbound edge.

        Used by the velocity rule: how fast does received money leave?
        """
        if not self.has_account(account_id):
            return None
        in_times = sorted(
            _as_utc(e.timestamp) for e in self.transactions_involving(account_id, direction="in"))
        if not in_times:
            return None
        edges = (self._g.edges(account_id, data=True) if direction == "out"
                 else self._g.in_edges(account_id, data=True))
        best = None
        for _s, _t, data in edges:
            ts = data["timestamp"]
            prior = [t for t in in_times if t <= ts]
            if not prior:
                continue
            gap = ts - max(prior)
            if best is None or gap < best:
                best = gap
        return best

    def forwarded_transactions(
        self, account_id: str, window_seconds: Optional[int] = None,
        as_of: Optional[datetime] = None,
    ) -> List[TransactionEvent]:
        """Outgoing transactions that have at least one prior inbound edge to the account."""
        if not self.has_account(account_id):
            return []
        as_of = _as_utc(as_of) if as_of is not None else utcnow()
        cutoff = as_of - timedelta(seconds=window_seconds) if window_seconds else None
        in_times = [t.timestamp_utc for t in self.transactions_involving(
            account_id, direction="in") if cutoff is None or t.timestamp_utc >= cutoff]
        if not in_times:
            return []
        out_events = []
        for _s, _t, data in self._g.edges(account_id, data=True):
            ev = data["txn"]
            if cutoff is not None and ev.timestamp_utc < cutoff:
                continue
            if any(t <= ev.timestamp_utc for t in in_times):
                out_events.append(ev)
        return out_events