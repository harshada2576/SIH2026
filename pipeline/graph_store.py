"""
pipeline/graph_store.py

In-memory graph representation of the transaction network.
Consumer.py calls add_transaction() for every Kafka event it reads.
Reference data (accounts, terminals) is loaded once at startup — it is NOT
streamed via Kafka, per the agreed schema (accounts.py / terminals.py output).

Design note: this deliberately does NOT touch ground-truth/scenario data.
The graph is built only from what a real system would actually see live.
"""

import networkx as nx
from collections import deque, defaultdict
from datetime import datetime, timedelta


def _parse_ts(ts):
    if isinstance(ts, datetime):
        return ts.replace(tzinfo=None) if ts.tzinfo is not None else ts
    if not isinstance(ts, str):
        raise ValueError(f"Timestamp must be string or datetime, got {type(ts)}")
    clean_ts = ts.replace("Z", "")
    try:
        dt = datetime.fromisoformat(clean_ts)
        return dt.replace(tzinfo=None)
    except ValueError:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                return datetime.strptime(clean_ts, fmt)
            except ValueError:
                continue
        raise ValueError(f"Unrecognized timestamp format: {ts}")


class GraphStore:
    def __init__(self, fan_window_seconds: int = 300):
        """
        fan_window_seconds: sliding window used for fan-in/fan-out counting
        (default 5 minutes — matches the kind of rapid-layering pattern
        the data generator injects).
        """
        self.graph = nx.MultiDiGraph()
        self.fan_window = timedelta(seconds=fan_window_seconds)

        # account_id -> deque of (timestamp, counterparty_id, direction) for windowed queries
        self._recent_activity = defaultdict(deque)

        # reference data, loaded once
        self.accounts = {}   # account_id -> dict
        self.terminals = {}  # terminal_id -> dict

        # device fingerprint index: device -> set of sending account_ids, account_id -> set of devices
        self._device_senders = defaultdict(set)
        self._account_devices = defaultdict(set)

        # transaction idempotence: set for O(1) duplicate checks + bounded time window
        self._seen_tx_ids = set()
        self._seen_tx_order = deque()

    # ---------- reference data loading ----------

    def load_accounts(self, accounts: list[dict]):
        for acc in accounts:
            self.accounts[acc["account_id"]] = acc
            if not self.graph.has_node(acc["account_id"]):
                self.graph.add_node(acc["account_id"], node_type="account", **acc)

    def load_terminals(self, terminals: list[dict]):
        for term in terminals:
            self.terminals[term["terminal_id"]] = term
            if not self.graph.has_node(term["terminal_id"]):
                self.graph.add_node(term["terminal_id"], node_type="terminal", **term)

    # ---------- live ingestion ----------

    def add_transaction(self, tx: dict) -> bool:
        """
        tx must match the locked 7-field transaction schema:
        transaction_id, source_account_id, target_account_id,
        amount_inr, timestamp, payment_channel, device_fingerprint

        Returns True if the transaction was accepted, or False if it was a duplicate.
        """
        tx_id = tx.get("transaction_id")
        if not tx_id:
            raise KeyError("transaction_id")

        if tx_id in self._seen_tx_ids:
            return False  # Idempotent: duplicate delivery has zero effect

        src, tgt = tx["source_account_id"], tx["target_account_id"]
        ts = _parse_ts(tx["timestamp"])
        dev = tx.get("device_fingerprint")

        self._seen_tx_ids.add(tx_id)
        self._seen_tx_order.append((ts, tx_id))
        self._prune_seen_tx(ts)

        for node in (src, tgt):
            if not self.graph.has_node(node):
                self.graph.add_node(node, node_type="account")

        self.graph.add_edge(
            src, tgt,
            transaction_id=tx_id,
            amount_inr=tx["amount_inr"],
            timestamp=ts,
            payment_channel=tx["payment_channel"],
            device_fingerprint=dev,
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
        retention = self.fan_window * 2
        self._seen_tx_order = deque(
            (ts, tid) for ts, tid in self._seen_tx_order if timedelta(0) <= (now - ts) <= retention
        )
        self._seen_tx_ids = {tid for _, tid in self._seen_tx_order}

    def _prune(self, account_id: str, now: datetime):
        dq = self._recent_activity[account_id]
        self._recent_activity[account_id] = deque(
            entry for entry in dq if timedelta(0) <= (now - entry[0]) <= self.fan_window
        )

    # ---------- structural signal queries (used by consumer to build graph_signals) ----------

    def fan_in_count(self, account_id: str) -> int:
        return sum(1 for _, _, d in self._recent_activity[account_id] if d == "in")

    def fan_out_count(self, account_id: str) -> int:
        return sum(1 for _, _, d in self._recent_activity[account_id] if d == "out")

    def distinct_counterparties_in_window(self, account_id: str) -> set:
        return {cp for _, cp, _ in self._recent_activity[account_id]}

    def shares_device_fingerprint(self, account_id: str) -> list[str]:
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

    def historical_terminal_affinity(self, account_id: str) -> list[str]:
        acc = self.accounts.get(account_id, {})
        return acc.get("historical_terminal_ids", [])

    def account_chain_depth(self, account_id: str, max_depth: int = 3) -> int:
        """
        Computes longest directed incoming path length within the sliding window,
        bounded to max_depth (0=source/isolated, 1=1-hop, 2=2-hop, 3=3+ hops).
        """
        visited = set()

        def _traverse_back(node: str, depth: int) -> int:
            if depth >= max_depth:
                return max_depth
            # get predecessors who sent money to `node` in the active window
            preds = {cp for _, cp, direction in self._recent_activity.get(node, []) if direction == "in"}
            unvisited_preds = preds - visited
            if not unvisited_preds:
                return depth
            visited.update(unvisited_preds)
            return max(_traverse_back(p, depth + 1) for p in unvisited_preds)

        return _traverse_back(account_id, 0)
