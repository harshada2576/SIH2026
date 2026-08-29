"""Rule registry — every rule in detection/rules/ is listed here exactly once."""
from __future__ import annotations

from typing import Callable, Dict

from detection.rules import (
    account_age_rule,
    amount_movement_rule,
    device_fingerprint_rule,
    fan_in_rule,
    fan_out_rule,
    layering_rule,
    terminal_affinity_rule,
    velocity_rule,
)

# name -> (evaluate function, human label) for the scorer to run + explain.
RULES: Dict[str, Callable] = {
    "velocity": velocity_rule.evaluate,
    "fan_in": fan_in_rule.evaluate,
    "fan_out": fan_out_rule.evaluate,
    "layering": layering_rule.evaluate,
    "amount_movement": amount_movement_rule.evaluate,
    "account_age": account_age_rule.evaluate,
    "device_fingerprint": device_fingerprint_rule.evaluate,
    "terminal_affinity": terminal_affinity_rule.evaluate,
}