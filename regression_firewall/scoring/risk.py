"""Risk score and verdict computation. Deterministic and explainable.

See docs/RISK_MODEL.md for the full model.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.change import Change
from .severity import POINTS, SEVERITIES


@dataclass
class Contribution:
    change_id: str
    description: str
    classification: str
    severity: str
    points: float


def score_changes(changes: list, thresholds) -> tuple:
    """Returns (score, verdict, score_floored, contributions).

    Verdict rules (in order):
      1. any UNEXPECTED CRITICAL            -> BLOCK
      2. any UNEXPECTED HIGH + block_on_high -> BLOCK
      3. score >= block_score               -> BLOCK
      4. any UNEXPECTED MEDIUM              -> REVIEW
      5. any UNCERTAIN change               -> REVIEW
      6. score >= review_score              -> REVIEW
      7. otherwise                          -> PASS

    When a rule (not the raw score) triggers BLOCK or REVIEW, the score is
    floored to the corresponding threshold so the number never contradicts
    the verdict; ``score_floored`` records that.
    """
    contributions = []
    total = 0.0
    for change in changes:
        if change.classification == "expected":
            contributions.append(Contribution(change.change_id, change.describe(),
                                               change.classification, change.severity, 0.0))
            continue
        points = POINTS.get(change.severity, 0) * change.confidence
        if change.classification == "uncertain":
            points *= 0.6
        total += points
        contributions.append(Contribution(change.change_id, change.describe(),
                                          change.classification, change.severity, round(points, 2)))

    score = int(round(min(100.0, total)))

    unexpected = [c for c in changes if c.classification == "unexpected"]
    uncertain = [c for c in changes if c.classification == "uncertain"]
    uncertain_present = bool(uncertain)
    # Content-level edits and medium+ uncertain changes always need a human
    # look; purely additive uncertain changes (new field, new symbol) do not
    # force a REVIEW on their own.
    UNCERTAIN_REVIEW_CATEGORIES = {"stdout_changed", "stderr_changed", "header_changed"}
    uncertain_needs_review = any(
        c.severity in ("medium", "high", "critical") or c.category in UNCERTAIN_REVIEW_CATEGORIES
        for c in uncertain
    )
    severities = [c.severity for c in unexpected]
    has = lambda s: s in severities  # noqa: E731

    floored = False
    if any(c == "critical" for c in severities):
        verdict = "BLOCK"
    elif has("high") and thresholds.block_on_high:
        verdict = "BLOCK"
    elif score >= thresholds.block_score:
        verdict = "BLOCK"
    elif any(c == "medium" for c in severities):
        verdict = "REVIEW"
    elif uncertain_needs_review:
        verdict = "REVIEW"
    elif score >= thresholds.review_score:
        verdict = "REVIEW"
    else:
        verdict = "PASS"

    # Floor the score only when the verdict rules demand a level the raw
    # score does not reach, so score and verdict never contradict.
    if verdict != "PASS":
        floor = thresholds.block_score if verdict == "BLOCK" else thresholds.review_score
        if score < floor:
            score = floor
            floored = True

    return score, verdict, floored, contributions


def severity_rank(severity: str) -> int:
    return SEVERITIES.index(severity)
