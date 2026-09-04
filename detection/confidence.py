"""detection/confidence.py — turns "risk score" into "how sure are we?".

Two independent 0-100 accounts can carry very different confidence: one
flagged by 6 agreeing rules is a much safer automated-action candidate than
one that crossed the threshold almost entirely on a single strong rule. This
module makes that distinction explicit and explainable, feeding
auto_intervention.py's decision on whether to act automatically or wait for a
human.

confidence = 0.6 * (fraction of rules that meaningfully fired)
           + 0.4 * (the ml_anomaly rule's own severity)

Both terms are already in [0, 1], so confidence is too. This is a
deliberately simple, auditable formula — not a second black-box model on top
of the first.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from detection.scorer import AccountEvaluation

AGREEMENT_THRESHOLD = 0.5  # a rule "meaningfully fired" if severity >= this


def compute_confidence(evaluation: "AccountEvaluation") -> float:
    if not evaluation.rules:
        return 0.0
    agreeing = [r for r in evaluation.rules if r.severity >= AGREEMENT_THRESHOLD]
    agreement_fraction = len(agreeing) / len(evaluation.rules)
    ml_severity = next((r.severity for r in evaluation.rules if r.name == "ml_anomaly"), 0.0)
    confidence = 0.6 * agreement_fraction + 0.4 * ml_severity
    return round(max(0.0, min(1.0, confidence)), 3)


def confidence_label(confidence: float) -> str:
    if confidence >= 0.75:
        return "HIGH"
    if confidence >= 0.45:
        return "MEDIUM"
    return "LOW"
