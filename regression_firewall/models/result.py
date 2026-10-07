from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Optional

from .change import Change

VERDICTS = ("PASS", "REVIEW", "BLOCK")


@dataclass
class CheckResult:
    """Outcome of one `regression-firewall check` run."""

    verdict: str
    score: int
    score_floored: bool = False
    changes: list = field(default_factory=list)  # list[Change]
    intent_source: str = "none"
    intent_task: Optional[str] = None
    intent_audit: dict = field(default_factory=dict)
    config_changed_since_baseline: bool = False
    baseline_trust_warning: bool = False
    warnings: list = field(default_factory=list)
    created_at: str = ""
    tool_version: str = ""
    project: dict = field(default_factory=dict)

    @property
    def summary(self) -> dict:
        counts = {"expected": 0, "unexpected": 0, "uncertain": 0}
        for change in self.changes:
            counts[change.classification] = counts.get(change.classification, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "schema_version": 1,
            "created_at": self.created_at,
            "tool_version": self.tool_version,
            "project": self.project,
            "verdict": self.verdict,
            "score": self.score,
            "score_floored": self.score_floored,
            "summary": self.summary,
            "intent": {"source": self.intent_source, "task": self.intent_task},
            "intent_audit": self.intent_audit,
            "config_changed_since_baseline": self.config_changed_since_baseline,
            "baseline_trust_warning": self.baseline_trust_warning,
            "warnings": list(self.warnings),
            "changes": [c.to_dict() for c in self.changes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CheckResult":
        return cls(
            verdict=d.get("verdict", "PASS"),
            score=int(d.get("score", 0)),
            score_floored=bool(d.get("score_floored", False)),
            changes=[Change.from_dict(c) for c in d.get("changes", [])],
            intent_source=(d.get("intent") or {}).get("source", "none"),
            intent_task=(d.get("intent") or {}).get("task"),
            intent_audit=d.get("intent_audit") or {},
            config_changed_since_baseline=bool(
                d.get("config_changed_since_baseline", False)
            ),
            baseline_trust_warning=bool(d.get("baseline_trust_warning", False)),
            warnings=list(d.get("warnings", [])),
            created_at=d.get("created_at", ""),
            tool_version=d.get("tool_version", ""),
            project=d.get("project") or {},
        )
