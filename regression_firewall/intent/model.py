"""Intent model: structured user intent used to classify behavior changes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class IntentError(ValueError):
    pass


@dataclass
class ExpectedChange:
    """One behavior change the user actually asked for.

    Field semantics (documented in intent files):
    - ``"*"`` on surface/target/category acts as a wildcard; target may be a
      fnmatch glob (e.g. ``GET /users/*``).
    - ``path`` optionally restricts field-level changes (fnmatch).
    - ``before`` / ``after`` constrain values when present and non-null; a
      JSON null means "unconstrained".
    """

    surface: str = "*"
    target: str = "*"
    category: str = "*"
    path: Optional[str] = None
    before: Any = None
    after: Any = None
    note: str = ""


@dataclass
class Intent:
    task: str = ""
    source: str = "none"  # "none" | "default" | a file path
    expected_changes: list = field(default_factory=list)  # list[ExpectedChange]


def load_intent(path: Path | None, source_label: str | None = None) -> Intent:
    if path is None or not Path(path).is_file():
        return Intent(source="none")
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise IntentError(f"{path}: invalid JSON: {e}") from e
    return intent_from_dict(raw, source=source_label or str(path))


def intent_from_dict(raw: dict, source: str = "intent") -> Intent:
    if not isinstance(raw, dict):
        raise IntentError(f"{source}: intent must be a JSON object")
    known = {"schema_version", "task", "expected_changes"}
    unknown = sorted(set(raw) - known)
    if unknown:
        raise IntentError(
            f"{source}: unknown intent keys: {', '.join(unknown)}. "
            f"Expected: {', '.join(sorted(known))}"
        )
    version = raw.get("schema_version", 1)
    if version != 1:
        raise IntentError(f"{source}: unsupported intent schema_version {version!r} (expected 1)")
    entries_raw = raw.get("expected_changes") or []
    if not isinstance(entries_raw, list):
        raise IntentError(f"{source}: 'expected_changes' must be a list")
    entries = []
    for i, entry in enumerate(entries_raw):
        if not isinstance(entry, dict):
            raise IntentError(f"{source}: expected_changes[{i}] must be an object")
        known_entry = {"surface", "target", "category", "path", "before", "after", "note"}
        unknown_entry = sorted(set(entry) - known_entry)
        if unknown_entry:
            raise IntentError(
                f"{source}: unknown keys in expected_changes[{i}]: {', '.join(unknown_entry)}"
            )
        entries.append(
            ExpectedChange(
                surface=str(entry.get("surface", "*")),
                target=str(entry.get("target", "*")),
                category=str(entry.get("category", "*")),
                path=entry.get("path"),
                before=entry.get("before"),
                after=entry.get("after"),
                note=str(entry.get("note", "")),
            )
        )
    return Intent(task=str(raw.get("task", "")), source=source, expected_changes=entries)
