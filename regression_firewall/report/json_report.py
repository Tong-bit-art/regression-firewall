from __future__ import annotations

from ..models.result import CheckResult
from ..scoring.risk import severity_rank
from ._explain import recommended_action, why_it_matters


def report_to_dict(result: CheckResult) -> dict:
    """Machine-readable report with per-change explanations attached."""
    data = result.to_dict()
    ordered = sorted(
        result.changes, key=lambda c: (-severity_rank(c.severity), c.target, c.category)
    )
    raw_by_id = {c.change_id: c.to_dict() for c in result.changes}
    enriched = []
    for change in ordered:
        entry = raw_by_id[change.change_id]
        entry["why_it_matters"] = why_it_matters(change.category)
        entry["recommended_action"] = recommended_action(change.category)
        enriched.append(entry)

    data["changes"] = enriched
    return data
