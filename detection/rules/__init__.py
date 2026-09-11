"""Rule registry — every rule in detection/rules/ is listed here exactly once."""
from __future__ import annotations

from typing import Callable, Dict

from detection.rules import (
    account_age_rule,
    amount_movement_rule,
    device_fingerprint_rule,
    fan_in_rule,
    fan_out_rule,
    geo_velocity_rule,
    identity_cluster_rule,
    layering_rule,
    ml_anomaly_rule,
    terminal_affinity_rule,
    velocity_rule,
)

# name -> (evaluate function, human label) for the scorer to run + explain.
# Phase 2 additions: geo_velocity, identity_cluster, ml_anomaly (see
# detection/scorer.py WEIGHTS for the rebalanced 11-rule weight table).
RULES: Dict[str, Callable] = {
    "velocity": velocity_rule.evaluate,
    "fan_in": fan_in_rule.evaluate,
    "fan_out": fan_out_rule.evaluate,
    "layering": layering_rule.evaluate,
    "amount_movement": amount_movement_rule.evaluate,
    "account_age": account_age_rule.evaluate,
    "device_fingerprint": device_fingerprint_rule.evaluate,
    "terminal_affinity": terminal_affinity_rule.evaluate,
    "geo_velocity": geo_velocity_rule.evaluate,
    "identity_cluster": identity_cluster_rule.evaluate,
    "ml_anomaly": ml_anomaly_rule.evaluate,
}