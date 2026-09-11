"""ML-anomaly rule: the "hybrid rule + ML" layer.

Trains a small unsupervised IsolationForest (scikit-learn) over the current
account population's behavioural feature vectors, and scores how anomalous
`account_id` looks relative to everyone else the graph has seen so far. This
is deliberately unsupervised (no labeled fraud data required — you never have
enough real labeled data at hackathon time) and deliberately cheap to retrain
(demo-scale graphs, a few hundred accounts at most).

If scikit-learn is unavailable, or the population is too small to fit a
meaningful model, this degrades to a transparent z-score fallback rather than
crashing the scorer — a rule that occasionally can't reach a verdict is fine;
a rule that takes the whole pipeline down is not.
"""
from __future__ import annotations

import statistics
from typing import Dict, List, Tuple

from pipeline.graph_store import GraphStore
from detection.rules.base import RuleResult

MIN_POPULATION_FOR_MODEL = 12


def _feature_vector(graph: GraphStore, account_id: str, window_seconds: int, as_of) -> List[float]:
    """Same behavioural signals the rule-based engine already computes —
    reused here as ML features instead of hand-tuned thresholds."""
    fan_in = graph.fan_in_count(account_id, window_seconds, as_of)
    fan_out = graph.fan_out_count(account_id, window_seconds, as_of)
    depth = graph.trail_depth(account_id, window_seconds, as_of=as_of)
    gap = graph.edge_latency_between(account_id, direction="out")
    velocity_seconds = gap.total_seconds() if gap is not None else window_seconds
    received = [e.amount_inr for e in graph.transactions_involving(account_id, window_seconds, "in", as_of)]
    total_received = sum(received) if received else 0.0
    return [float(fan_in), float(fan_out), float(depth), float(velocity_seconds), float(total_received)]


def _population_vectors(graph: GraphStore, window_seconds: int, as_of) -> Dict[str, List[float]]:
    account_ids = [
        n for n, data in graph.graph.nodes(data=True)
        if data.get("node_type") == "account" or n in graph.accounts
    ]
    return {aid: _feature_vector(graph, aid, window_seconds, as_of) for aid in account_ids}


def _zscore_fallback(vectors: Dict[str, List[float]], account_id: str) -> Tuple[float, str]:
    """Simple statistical anomaly score when the population is too small for
    a stable IsolationForest fit."""
    if account_id not in vectors or len(vectors) < 3:
        return 0.0, "population too small to assess anomaly"
    dim = len(vectors[account_id])
    z_scores = []
    for i in range(dim):
        col = [v[i] for v in vectors.values()]
        mean = statistics.fmean(col)
        stdev = statistics.pstdev(col) or 1.0
        z_scores.append(abs((vectors[account_id][i] - mean) / stdev))
    max_z = max(z_scores)
    severity = max(0.0, min(1.0, (max_z - 1.0) / 3.0))  # z=1 -> 0.0, z=4+ -> 1.0
    return severity, f"max feature z-score {max_z:.1f} vs. current population"


def _isolation_forest_score(vectors: Dict[str, List[float]], account_id: str) -> Tuple[float, str]:
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return _zscore_fallback(vectors, account_id)

    ids = list(vectors.keys())
    X = [vectors[i] for i in ids]
    model = IsolationForest(n_estimators=100, contamination="auto", random_state=42)
    model.fit(X)
    scores = model.decision_function(X)  # higher = more normal, lower/negative = more anomalous
    idx = ids.index(account_id)
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return 0.0, "no separation in current population"
    # invert + normalize so 0 = most normal, 1 = most anomalous
    severity = float((hi - scores[idx]) / (hi - lo))
    return severity, f"isolation-forest anomaly percentile {severity:.0%} vs. {len(ids)} accounts"


_MODEL_CACHE: Dict[Tuple, Tuple[Any, float, float, str]] = {}


def evaluate(graph: GraphStore, account_id: str, window_seconds: int = 3600,
             as_of=None) -> RuleResult:
    if not graph.has_account(account_id):
        return RuleResult(
            "ml_anomaly", 0.0, "account not yet in graph",
            "ML anomaly: account has no observed behaviour yet").clamped()

    # Step 1: Compute feature vector for this specific account
    v = _feature_vector(graph, account_id, window_seconds, as_of)

    # Step 2: Get or fit baseline model (refreshed periodically)
    num_edges = graph.graph.number_of_edges()
    model_key = (id(graph), num_edges // 500)

    if model_key in _MODEL_CACHE:
        model, lo, hi, model_name = _MODEL_CACHE[model_key]
    else:
        # Sample active accounts to fit baseline model
        all_accs = [
            n for n, data in graph.graph.nodes(data=True)
            if data.get("node_type") == "account" or n in graph.accounts or n in graph._metadata
        ]
        sample_accs = all_accs[:150] if len(all_accs) > 150 else all_accs
        if account_id not in sample_accs:
            sample_accs.append(account_id)
        vectors = {aid: _feature_vector(graph, aid, window_seconds, as_of) for aid in sample_accs}

        if len(vectors) < MIN_POPULATION_FOR_MODEL:
            model, lo, hi, model_name = None, 0.0, 1.0, "statistical fallback"
        else:
            try:
                from sklearn.ensemble import IsolationForest
                X = list(vectors.values())
                m = IsolationForest(n_estimators=50, contamination="auto", random_state=42)
                m.fit(X)
                raw = m.decision_function(X)
                lo, hi = float(min(raw)), float(max(raw))
                model, model_name = m, "IsolationForest"
            except ImportError:
                model, lo, hi, model_name = None, 0.0, 1.0, "statistical fallback (scikit-learn missing)"

        if len(_MODEL_CACHE) > 8:
            _MODEL_CACHE.clear()
        _MODEL_CACHE[model_key] = (model, lo, hi, model_name)

    # Step 3: Score the account
    if model is not None and (hi - lo) > 1e-9:
        score = float(model.decision_function([v])[0])
        severity = float(max(0.0, min(1.0, (hi - score) / (hi - lo))))
        detail = f"isolation-forest anomaly percentile {severity:.0%}"
    else:
        # Statistical rule of thumb on feature vector
        # [fan_in, fan_out, depth, velocity_seconds, total_received]
        anom = 0.0
        if v[0] >= 5:  # High fan-in
            anom += 0.4
        if v[1] >= 5:  # High fan-out
            anom += 0.4
        if v[2] >= 3:  # Deep chain
            anom += 0.3
        if v[4] > 50000:  # High amount received
            anom += 0.3
        if v[3] < 120 and v[4] > 50000:  # Rapid high-value velocity
            anom += 0.4
        severity = max(0.0, min(1.0, anom))
        detail = f"feature anomaly heuristic score {severity:.2f}"

    measured = f"[{model_name}] {detail}"
    evidence = (
        f"ML anomaly ({model_name}): {account_id}'s behaviour is a statistical outlier "
        f"vs. the rest of the account population ({detail})" if severity >= 0.6 else
        f"ML anomaly: behaviour within normal range for the current population"
    )
    return RuleResult("ml_anomaly", severity, measured, evidence).clamped()
