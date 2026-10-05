from __future__ import annotations

from ..config.schema import Config
from ..models.change import MISSING, Change
from ..scoring.severity import confidence_for, severity_for


def json_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _child(path: str, key: str) -> str:
    return f"{path}.{key}" if path else str(key)


def diff_json(before, after, path: str = "$") -> list:
    """Structural JSON comparison. Returns a list of
    {path, category, before, after} entries with categories:
    field_removed, field_added, field_type_changed, value_changed,
    list_size_changed, response_shape_changed (root container type flip).

    A side that did not have the value at all is represented by
    ``models.change.MISSING`` (rendered as null with a presence flag).
    """
    out = []
    _diff(before, after, path, out)
    return out


def _diff(before, after, path: str, out: list) -> None:
    type_before, type_after = json_type(before), json_type(after)
    if type_before != type_after:
        category = "response_shape_changed" if path == "$" else "field_type_changed"
        out.append({"path": path, "category": category, "before": before, "after": after})
        return
    if type_before == "object":
        for key in sorted(set(before) - set(after)):
            out.append({"path": _child(path, key), "category": "field_removed",
                        "before": before[key], "after": MISSING})
        for key in sorted(set(after) - set(before)):
            out.append({"path": _child(path, key), "category": "field_added",
                        "before": MISSING, "after": after[key]})
        for key in sorted(set(before) & set(after)):
            _diff(before[key], after[key], _child(path, key), out)
    elif type_before == "array":
        if len(before) != len(after):
            out.append({"path": path, "category": "list_size_changed",
                        "before": len(before), "after": len(after)})
        for index in range(min(len(before), len(after))):
            _diff(before[index], after[index], f"{path}[{index}]", out)
    else:
        if before != after:
            out.append({"path": path, "category": "value_changed",
                        "before": before, "after": after})


def _resolve_severity(surface: str, category: str, hint, config: Config | None) -> str:
    """Config overrides win over the diff-stage's contextual hint, which wins
    over the static per-category default."""
    overrides = config.severity_overrides if config else {}
    override = overrides.get(f"{surface}:{category}") or overrides.get(category)
    return override or hint or severity_for(surface, category)


def make_change(surface: str, target: str, entry_or_category, path=None,
                before=MISSING, after=MISSING, evidence=None, description="",
                severity=None, config: Config | None = None) -> Change:
    if isinstance(entry_or_category, dict):
        category = entry_or_category["category"]
        path = entry_or_category.get("path")
        before = entry_or_category.get("before", MISSING)
        after = entry_or_category.get("after", MISSING)
    else:
        category = entry_or_category
    change = Change(
        surface=surface,
        target=target,
        category=category,
        path=path,
        before=before,
        after=after,
        evidence=evidence or {},
        description=description,
        confidence=confidence_for(category),
    )
    change.severity = _resolve_severity(surface, category, severity, config)
    return change

