"""Deterministic SQL shape normalization for database-behavior tracing.

A "shape" is the query with literal values replaced by placeholders and
whitespace/comments collapsed — the same query with different parameters
must produce the same shape, so a diff shows *query-set* changes, not data.
Pure functions; no SQL parsing beyond targeted regexes (this is not a
parser — exotic SQL that defeats the regexes still produces a stable,
if less-collapsed, shape).
"""

from __future__ import annotations

import re

_STRING_LITERALS = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")
_NUMBER_LITERALS = re.compile(r"(?<![\w.])(?:\d+\.\d+|\d+)(?![\w.])")
_LINE_COMMENTS = re.compile(r"--[^\n]*")
_BLOCK_COMMENTS = re.compile(r"/\*.*?\*/", re.S)
_WHITESPACE = re.compile(r"\s+")
_IN_OPERATOR = re.compile(r"\bIN\s*\([^()]*\)", re.I)

# Write targets: INSERT [OR ...] INTO tbl / REPLACE INTO tbl / UPDATE tbl /
# DELETE FROM tbl / CREATE|DROP|ALTER TABLE tbl
_WRITE_TARGET = re.compile(
    r"\b(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM|"
    r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|DROP\s+TABLE(?:\s+IF\s+EXISTS)?|"
    r"ALTER\s+TABLE)\s+[\"'`\[]?(\w+)",
    re.I,
)


def sql_shape(sql: str) -> str:
    """Normalized query shape. Deterministic: same SQL text (modulo literal
    values, comments, and whitespace) yields the same shape."""
    text = _BLOCK_COMMENTS.sub(" ", sql)
    text = _LINE_COMMENTS.sub(" ", text)
    text = _STRING_LITERALS.sub("?", text)
    text = _IN_OPERATOR.sub("IN (?)", text, count=0)
    text = _NUMBER_LITERALS.sub("?", text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text


def write_targets(shape_or_sql: str) -> set:
    """Table names written by a statement (best-effort, stdlib-SQL-grade)."""
    return {m.group(1) for m in _WRITE_TARGET.finditer(shape_or_sql)}
