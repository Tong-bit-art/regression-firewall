from __future__ import annotations

import fnmatch
import json

from ..models.change import Change
from .model import Intent

# Categories where an unmatched change is reported as UNCERTAIN rather than
# UNEXPECTED: the diff is real, but whether it is a regression needs judgment
# (additive or content-level changes are frequently intentional).
UNCERTAIN_CATEGORIES = {
    "value_changed",
    "list_size_changed",
    "stdout_changed",
    "stderr_changed",
    "header_changed",
    "field_added",
    "symbol_added",
    "file_created",
    "file_modified",
}


def matching_entries(change: Change, intent: Intent) -> list:
    """All intent entries that match this change, in file order."""
    return [expected for expected in intent.expected_changes
            if _entry_matches(change, expected)]


def _entry_matches(change: Change, expected) -> bool:
    if expected.surface not in ("*", change.surface):
        return False
    if not fnmatch.fnmatchcase(change.target, expected.target):
        return False
    if expected.category not in ("*", change.category):
        return False
    if expected.path and not fnmatch.fnmatchcase(_intent_path(change.path), expected.path):
        return False
    if expected.before is not None and not _values_equal(change.before, expected.before):
        return False
    if expected.after is not None and not _values_equal(change.after, expected.after):
        return False
    return True


def classify_change(change: Change, intent: Intent) -> tuple:
    """Returns (classification, matched_note).

    classification is "expected" (matched intent), "uncertain", or
    "unexpected". Uncertainty is never resolved silently: UNCERTAIN changes
    drive a REVIEW verdict.
    """
    matches = matching_entries(change, intent)
    if matches:
        return "expected", (matches[0].note or None)
    if change.category in UNCERTAIN_CATEGORIES:
        return "uncertain", None
    return "unexpected", None


def _intent_path(path) -> str:
    """Changes carry JSON paths like '$.user.items[0].name'; intent files
    refer to the same location as 'user.items.*.name': the '$.' prefix is
    stripped and bracket array indices become dotted segments so '*' can
    match them (header names have no prefix either way)."""
    import re

    text = path or ""
    if text.startswith("$."):
        text = text[2:]
    return re.sub(r"\[(\d+)\]", r".", text)


def _values_equal(change_value, intent_value) -> bool:
    """Intent constraint satisfaction. Absent-side (MISSING) never matches,
    so an expectation of ``before: 401`` only matches a real before value."""
    from ..models.change import MISSING, is_missing

    if is_missing(change_value):
        return False
    return _canonical(change_value) == _canonical(intent_value)


def _canonical(value) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)
