from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

# Sentinel for "value did not exist on this side" in a change. Serialized as
# JSON null plus a companion flag so reports can distinguish "empty" from
# "absent".
MISSING = object()


def is_missing(value: Any) -> bool:
    return value is MISSING


def _jsonify(value: Any) -> Any:
    if is_missing(value):
        return None
    return value


@dataclass
class Change:
    """One detected behavioral difference between baseline and latest."""

    surface: str
    target: str
    category: str
    before: Any = MISSING
    after: Any = MISSING
    path: Optional[str] = None
    evidence: dict = field(default_factory=dict)
    description: str = ""
    classification: str = "uncertain"  # expected | unexpected | uncertain
    severity: str = "low"  # info | low | medium | high | critical
    confidence: float = 0.95
    note: Optional[str] = None

    @property
    def change_id(self) -> str:
        raw = "|".join(
            [self.surface, self.target, self.category, self.path or ""]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["before"] = _jsonify(self.before)
        d["after"] = _jsonify(self.after)
        d["before_present"] = not is_missing(self.before)
        d["after_present"] = not is_missing(self.after)
        d["change_id"] = self.change_id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Change":
        return cls(
            surface=d["surface"],
            target=d["target"],
            category=d["category"],
            before=d.get("before"),
            after=d.get("after"),
            path=d.get("path"),
            evidence=d.get("evidence") or {},
            description=d.get("description") or "",
            classification=d.get("classification", "uncertain"),
            severity=d.get("severity", "low"),
            confidence=d.get("confidence", 0.95),
            note=d.get("note"),
        )

    def describe(self) -> str:
        if self.description:
            return self.description
        before = _render(self.before)
        after = _render(self.after)
        location = f"{self.target} {self.path}" if self.path else self.target
        return f"{location}: {self.category} ({before} -> {after})"


def _render(value: Any) -> str:
    if is_missing(value):
        return "<absent>"
    if isinstance(value, str):
        return value if len(value) <= 80 else value[:77] + "..."
    if isinstance(value, (dict, list)):
        import json

        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return text if len(text) <= 80 else text[:77] + "..."
    return str(value)
