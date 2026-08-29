"""
detection/scorer.py

Consumes the "graph_signals" Kafka topic, applies explainable heuristic rules
(Fan-In, Fan-Out, Layering/Chain-Depth, Device Fingerprint Reuse), and publishes
risk_alert events matching the Architecture.md contract.

Detection Architecture:
- Independent modular rule evaluators returning (score: float, evidence: str | None).
- Dominant-rule aggregation (max-pooling over active rule violations with multi-motif synergy).
- Terminal prediction based on historical affinity.
"""

import csv
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from kafka import KafkaConsumer, KafkaProducer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scorer")

KAFKA_BOOTSTRAP = "localhost:9092"
SIGNALS_TOPIC = "graph_signals"
ALERTS_TOPIC = "risk_alerts"

# Calibrated alert threshold: any dominant rule firing at >= 0.70 produces an alert
ALERT_THRESHOLD = 0.70


# ============================================================================
# INDEPENDENT MODULAR DETECTION RULES
# ============================================================================

def evaluate_fan_in_rule(signal: dict) -> tuple[float, str | None]:
    """
    Rule 1: Fan-In Aggregation Detection.
    Detects sudden multi-account fund transfers into a single recipient within the sliding window.
    """
    fan_in = signal.get("fan_in_count", 0)
    if fan_in >= 3:
        # Scales: 3 txns -> 0.70, 4 txns -> 0.85, 5+ txns -> 1.00
        score = 0.70 + 0.30 * min(fan_in - 3, 2) / 2.0
        evidence = f"Rapid fan-in: {fan_in} accounts transferred funds within the 5-minute window"
        return round(min(score, 1.0), 3), evidence
    return 0.0, None


def evaluate_fan_out_rule(signal: dict) -> tuple[float, str | None]:
    """
    Rule 2: Fan-Out Dispersion Detection.
    Detects a single source account rapidly dispersing funds to multiple recipients.
    """
    fan_out = signal.get("fan_out_count", 0)
    if fan_out >= 3:
        # Scales: 3 txns -> 0.70, 4 txns -> 0.85, 5+ txns -> 1.00
        score = 0.70 + 0.30 * min(fan_out - 3, 2) / 2.0
        evidence = f"Rapid fan-out: Dispersed funds to {fan_out} accounts within the 5-minute window"
        return round(min(score, 1.0), 3), evidence
    return 0.0, None


def evaluate_layering_rule(signal: dict) -> tuple[float, str | None]:
    """
    Rule 3: Multi-Hop Layering / Chain-Depth Detection.
    Detects intermediate pass-through nodes and aggregator sinks in active layering chains.
    """
    depth = signal.get("chain_depth", 0)
    active_in_window = (signal.get("fan_in_count", 0) >= 1 or signal.get("fan_out_count", 0) >= 1)

    if depth >= 3 and active_in_window:
        return 0.95, "Multi-hop layering: Account sits at depth 3+ in an active transaction chain (aggregator node)"
    elif depth == 2 and active_in_window:
        return 0.75, "Intermediate layering: Account is a pass-through node (depth 2) in a rapid multi-hop chain"
    return 0.0, None


def evaluate_device_rule(signal: dict) -> tuple[float, str | None]:
    """
    Rule 4: Device Fingerprint Reuse Detection.
    Detects multiple distinct sender accounts initiating transactions from the same physical device.
    """
    shared = signal.get("shared_device_accounts", [])
    if shared:
        return 0.90, f"Device reuse: Hardware fingerprint shared with {len(shared)} other sending account(s)"
    return 0.0, None


# ============================================================================
# AGGREGATION & ALERT GENERATION
# ============================================================================

def evaluate_all_rules(signal: dict) -> list[tuple[float, str | None]]:
    """Evaluates all 4 modular detection rules against the signal."""
    return [
        evaluate_fan_in_rule(signal),
        evaluate_fan_out_rule(signal),
        evaluate_layering_rule(signal),
        evaluate_device_rule(signal),
    ]


def score_signal(signal: dict) -> float:
    """
    Dominant-rule aggregation: Takes the maximum score across all active rules,
    with a minor synergy boost (+0.05) if multiple distinct rules fire.
    """
    rule_results = evaluate_all_rules(signal)
    rule_scores = [score for score, _ in rule_results if score > 0.0]

    if not rule_scores:
        # Baseline structural score for normal low-volume activity (0.00 - 0.20)
        bg = 0.05 * min(signal.get("distinct_counterparties", 0), 2) + 0.04 * min(signal.get("chain_depth", 0), 1)
        return round(min(bg, 0.25), 3)

    dominant_score = max(rule_scores)
    synergy_boost = 0.05 if len(rule_scores) > 1 else 0.0
    return round(min(dominant_score + synergy_boost, 1.0), 3)


def build_evidence(signal: dict) -> list[str]:
    """Extracts human-readable evidence strings from all triggered rules."""
    rule_results = evaluate_all_rules(signal)
    evidence = [ev for score, ev in rule_results if score >= 0.50 and ev is not None]
    return evidence or ["Elevated structural activity, below strong-evidence thresholds"]


# ============================================================================
# TERMINAL REFERENCE DATA & PREDICTION
# ============================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
TERMINALS_CSV_PATH = REPO_ROOT / "data" / "output" / "terminals.csv"

# Global terminal coordinates cache: terminal_id -> {"latitude": float, "longitude": float}
TERMINAL_COORDS = {}


def load_terminal_reference_data(csv_path: Path | str = TERMINALS_CSV_PATH) -> dict[str, dict]:
    """Loads terminal latitude and longitude from reference CSV."""
    global TERMINAL_COORDS
    if TERMINAL_COORDS:
        return TERMINAL_COORDS

    path = Path(csv_path)
    if not path.exists():
        log.warning(f"Terminals reference file not found at {path}")
        return {}

    coords = {}
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t_id = row.get("terminal_id")
            if t_id:
                coords[t_id] = {
                    "latitude": float(row["latitude"]) if row.get("latitude") else None,
                    "longitude": float(row["longitude"]) if row.get("longitude") else None,
                }
    TERMINAL_COORDS = coords
    return TERMINAL_COORDS


def predict_terminals(signal: dict) -> list[dict]:
    """
    Predicts likely physical cash-out terminals based on known historical affinity.
    Decays confidence by rank for top 3 terminals and attaches physical geo-coordinates
    matching Architecture.md §6.4.
    """
    terminals = signal.get("historical_terminal_ids", [])
    if not terminals:
        return []

    if not TERMINAL_COORDS:
        load_terminal_reference_data()

    base = 0.9
    predictions = []
    for i, t in enumerate(terminals[:3]):
        coord = TERMINAL_COORDS.get(t, {})
        pred = {
            "terminal_id": t,
            "probability": round(base * (0.7 ** i), 2),
            "latitude": coord.get("latitude"),
            "longitude": coord.get("longitude"),
        }
        predictions.append(pred)
    return predictions


def build_alert(signal: dict) -> dict:
    """Constructs the locked Risk Alert JSON payload."""
    raw_ts = signal.get("timestamp", "")
    try:
        now = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except Exception:
        now = datetime.now()

    return {
        "complaint_id": f"SYN-{uuid.uuid4().hex[:8]}",
        "risk_score": score_signal(signal),
        "flagged_account_id": signal["account_id"],
        "predicted_terminals": predict_terminals(signal),
        "evidence": build_evidence(signal),
        "predicted_window_start": now.isoformat(),
        "predicted_window_end": (now + timedelta(minutes=45)).isoformat(),
    }


# ============================================================================
# KAFKA CONSUMER & DISPATCHER LOOP
# ============================================================================

def run():
    consumer = KafkaConsumer(
        SIGNALS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        group_id="scorer-group",
    )
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    log.info("Scorer started, listening for graph_signals...")

    for message in consumer:
        signal = message.value
        risk_score = score_signal(signal)

        if risk_score >= ALERT_THRESHOLD:
            alert = build_alert(signal)
            producer.send(ALERTS_TOPIC, value=alert)
            log.info(f"ALERT: {alert}")

    producer.flush()


if __name__ == "__main__":
    run()

