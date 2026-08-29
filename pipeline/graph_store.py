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
        return ts
    # accepts "2026-08-29T10:03:21Z" or "2026-08-29 10:03:21"
    ts = ts.replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
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

    def add_transaction(self, tx: dict):
        """
        tx must match the locked 7-field transaction schema:
        transaction_id, source_account_id, target_account_id,
        amount_inr, timestamp, payment_channel, device_fingerprint
        """
        src, tgt = tx["source_account_id"], tx["target_account_id"]
        ts = _parse_ts(tx["timestamp"])

        for node in (src, tgt):
            if not self.graph.has_node(node):
                self.graph.add_node(node, node_type="account")

        self.graph.add_edge(
            src, tgt,
            transaction_id=tx["transaction_id"],
            amount_inr=tx["amount_inr"],
            timestamp=ts,
            payment_channel=tx["payment_channel"],
            device_fingerprint=tx["device_fingerprint"],
        )

        self._recent_activity[src].append((ts, tgt, "out"))
        self._recent_activity[tgt].append((ts, src, "in"))
        self._prune(src, ts)
        self._prune(tgt, ts)

    def _prune(self, account_id: str, now: datetime):
        dq = self._recent_activity[account_id]
        while dq and (now - dq[0][0]) > self.fan_window:
            dq.popleft()

    # ---------- structural signal queries (used by consumer to build graph_signals) ----------

    def fan_in_count(self, account_id: str) -> int:
        return sum(1 for _, _, d in self._recent_activity[account_id] if d == "in")

    def fan_out_count(self, account_id: str) -> int:
        return sum(1 for _, _, d in self._recent_activity[account_id] if d == "out")

    def distinct_counterparties_in_window(self, account_id: str) -> set:
        return {cp for _, cp, _ in self._recent_activity[account_id]}

    def shares_device_fingerprint(self, account_id: str) -> list[str]:
        """Return other accounts that have transacted using the same device fingerprint."""
        fps = set()
        for _, _, data in self.graph.in_edges(account_id, data=True):
            fps.add(data.get("device_fingerprint"))
        for _, _, data in self.graph.out_edges(account_id, data=True):
            fps.add(data.get("device_fingerprint"))

        matches = []
        for u, v, data in self.graph.edges(data=True):
            if data.get("device_fingerprint") in fps and u != account_id and v != account_id:
                matches.extend([u, v])
        return list(set(matches))

    def historical_terminal_affinity(self, account_id: str) -> list[str]:
        acc = self.accounts.get(account_id, {})
        return acc.get("historical_terminal_ids", [])

    def account_chain_depth(self, account_id: str) -> int:
        """Rough proxy for how deep in a mule chain this account sits (victim=0)."""
        tier = self.accounts.get(account_id, {}).get("account_tier", "")
        return {"victim": 0, "mule_l1": 1, "mule_l2": 2, "aggregator": 3}.get(tier, -1)
