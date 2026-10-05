"""Severity tables, points, and confidence classes."""

from __future__ import annotations

SEVERITIES = ("info", "low", "medium", "high", "critical")

POINTS = {"info": 0, "low": 4, "medium": 20, "high": 34, "critical": 55}

# Default severity per (surface, category). See docs/BEHAVIOR_MODEL.md.
DEFAULT_SEVERITY = {
    ("http", "status_changed"): "high",
    ("http", "field_removed"): "high",
    ("http", "field_added"): "low",
    ("http", "field_type_changed"): "medium",
    ("http", "response_shape_changed"): "medium",
    ("http", "value_changed"): "low",
    ("http", "list_size_changed"): "low",
    ("http", "content_type_changed"): "medium",
    ("http", "header_changed"): "low",
    ("http", "cookie_changed"): "medium",
    ("http", "capture_error"): "high",
    ("cli", "exit_code_changed"): "high",
    ("cli", "stdout_changed"): "low",
    ("cli", "stderr_changed"): "low",
    ("cli", "file_created"): "medium",
    ("cli", "file_deleted"): "high",
    ("cli", "file_modified"): "medium",
    ("cli", "capture_error"): "high",
    ("public_api", "symbol_removed"): "critical",
    ("public_api", "symbol_added"): "info",
    ("public_api", "signature_changed"): "medium",
    ("public_api", "export_changed"): "medium",
    ("public_api", "capture_error"): "high",
}

# Categories whose *detection* is value-level rather than structural, so a
# detected difference is slightly less certain to be a real behavior change.
VALUE_LEVEL_CATEGORIES = {
    "value_changed",
    "list_size_changed",
    "stdout_changed",
    "stderr_changed",
    "header_changed",
}

STATE_CATEGORIES = {"capture_error"}

CONFIDENCE_STRUCTURAL = 0.95
CONFIDENCE_VALUE = 0.75
CONFIDENCE_STATE = 0.9


def default_severity(surface: str, category: str) -> str:
    return DEFAULT_SEVERITY[(surface, category)]


def severity_for(surface: str, category: str, overrides: dict | None = None) -> str:
    overrides = overrides or {}
    override = overrides.get(f"{surface}:{category}") or overrides.get(category)
    return override or default_severity(surface, category)


def confidence_for(category: str) -> float:
    if category in STATE_CATEGORIES:
        return CONFIDENCE_STATE
    if category in VALUE_LEVEL_CATEGORIES:
        return CONFIDENCE_VALUE
    return CONFIDENCE_STRUCTURAL
