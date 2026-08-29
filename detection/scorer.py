"""
detection/scorer.py

Consumes the "graph_signals" topic (published by pipeline/consumer.py) and
applies explainable heuristic rules — NOT a trained model, per Rules.md —
to produce risk_alert events matching the Architecture.md contract.

Owned by the detection workstream. Handed off as a starting point; confirm
ownership/edits with them before diverging.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from kafka import KafkaConsumer, KafkaProducer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scorer")

KAFKA_BOOTSTRAP = "localhost:9092"
SIGNALS_TOPIC = "graph_signals"
ALERTS_TOPIC = "risk_alerts"

# tune these once real synthetic volumes are in
WEIGHTS = {
    "fan_in": 0.3,
    "fan_out": 0.2,
    "shared_device": 0.25,
    "chain_depth": 0.15,
    "distinct_counterparties": 0.1,
}
ALERT_THRESHOLD = 0.6


def score_signal(signal: dict) -> float:
    fan_in = min(signal["fan_in_count"] / 5, 1.0)
    fan_out = min(signal["fan_out_count"] / 5, 1.0)
    shared_device = 1.0 if signal["shared_device_accounts"] else 0.0
    chain_depth = max(signal["chain_depth"], 0) / 3
    distinct_cp = min(signal["distinct_counterparties"] / 5, 1.0)

    score = (
        WEIGHTS["fan_in"] * fan_in
        + WEIGHTS["fan_out"] * fan_out
        + WEIGHTS["shared_device"] * shared_device
        + WEIGHTS["chain_depth"] * chain_depth
        + WEIGHTS["distinct_counterparties"] * distinct_cp
    )
    return round(min(score, 1.0), 3)


def build_evidence(signal: dict) -> list[str]:
    evidence = []
    if signal["fan_in_count"] >= 3:
        evidence.append(f"Fan-in of {signal['fan_in_count']} accounts within the recent window")
    if signal["fan_out_count"] >= 3:
        evidence.append(f"Fan-out to {signal['fan_out_count']} accounts within the recent window")
    if signal["shared_device_accounts"]:
        evidence.append(
            f"Shares device fingerprint with {len(signal['shared_device_accounts'])} other account(s)"
        )
    if signal["chain_depth"] == 3:
        evidence.append("Account classified as aggregator tier — funds likely consolidating for cash-out")
    return evidence or ["Elevated structural activity, below strong-evidence thresholds"]


def predict_terminals(signal: dict) -> list[dict]:
    """
    Naive terminal prediction using historical affinity only. Real version
    would weight by terminal proximity/recency too — fine to extend later.
    """
    terminals = signal.get("historical_terminal_ids", [])
    if not terminals:
        return []
    # even split of confidence across known historical terminals, decayed by rank
    base = 0.9
    return [
        {"terminal_id": t, "probability": round(base * (0.7 ** i), 2)}
        for i, t in enumerate(terminals[:3])
    ]


def build_alert(signal: dict) -> dict:
    now = datetime.fromisoformat(signal["timestamp"])
    return {
        "complaint_id": f"SYN-{uuid.uuid4().hex[:8]}",
        "risk_score": score_signal(signal),
        "flagged_account_id": signal["account_id"],
        "predicted_terminals": predict_terminals(signal),
        "evidence": build_evidence(signal),
        "predicted_window_start": now.isoformat(),
        "predicted_window_end": (now + timedelta(minutes=45)).isoformat(),
    }


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
