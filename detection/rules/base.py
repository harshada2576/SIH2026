"""Shared scaffolding for detection rules (Rules.md section 3: one file per rule).

Each rule returns a `RuleResult` with a *normalized severity in [0, 1]*.
The scorer multiplies severity by the rule's configured weight to get points,
so the weight of a signal lives in ONE place (detection/scorer.py) and every
rule stays independently testable.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuleResult:
    """Outcome of one rule against one account."""

    name: str
    severity: float  # 0..1, how strongly the signal fired (already thresholded)
    measured: str    # the raw value this rule measured, human-readable
    evidence: str    # full explainability sentence for the alert's evidence[] list

    def clamped(self) -> "RuleResult":
        """Return a copy with severity clamped to [0, 1]."""
        self.severity = max(0.0, min(1.0, self.severity))
        return self


def count_bins(value: int, bins) -> float:
    """Map an integer measurement to a 0..1 severity using (threshold, severity) bins.

    Example: count_bins(6, [(2,0.0),(4,0.5),(7,0.75),(100,1.0)]) -> 0.75
    """
    sev = 0.0
    for threshold, s in bins:
        if value >= threshold:
            sev = s
        else:
            break
    return sev