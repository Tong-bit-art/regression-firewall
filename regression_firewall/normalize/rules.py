"""Normalization rules: regexes, key-hint patterns, and helpers.

Rules are pure functions of (value, key-context, config-flags). They are
ordered: value-shape rules run before key-hint rules. See docs/NORMALIZATION.md.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
UUID_INLINE_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# 2026-10-04, 2026-10-04T22:41:00, 2026-10-04 22:41:00.123456+02:00, ...
ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?(Z|[+-]\d{2}:?\d{2})?)?$"
)
ISO_INLINE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
)

# Key-name hints. Applied only when the key looks temporal / identity-ish so
# business IDs are never masked. All of these are additionally guarded by the
# epoch range check (values outside 1e9-2e13 are never masked).
TEMPORAL_KEY_RE = re.compile(
    r"(timestamp|_ts$|^ts$|_at$|[a-z]At$|[a-z]Time$|^date$|_date$|^time$|_time$"
    r"|_ms$|^expires|_expires$)",
    re.I,
)
REQUEST_ID_KEY_RE = re.compile(
    r"(request[_-]?id|correlation[_-]?id|trace[_-]?id|x-request-id|x-correlation-id|x-trace-id)",
    re.I,
)
TOKEN_KEY_RE = re.compile(
    r"(token|secret|nonce|api[_-]?key|apikey|passw(or)?d|session|csrf|authorization"
    r"|credential|jwt|bearer|private[_-]?key|access[_-]?key|(?<![a-z])auth(?![a-z]))",
    re.I,
)
DURATION_KEY_RE = re.compile(r"(duration|elapsed|latency|took)", re.I)

ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

EPOCH_SECONDS_MIN, EPOCH_SECONDS_MAX = 10**9, 2 * 10**10
EPOCH_MILLIS_MIN, EPOCH_MILLIS_MAX = 10**12, 2 * 10**13

_TEMP_ROOTS = ("/tmp/", "/var/folders/", "appdata\\local\\temp", "\\temp\\", "temp\\")


def looks_like_epoch(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return EPOCH_SECONDS_MIN <= value <= EPOCH_SECONDS_MAX or (
            EPOCH_MILLIS_MIN <= value <= EPOCH_MILLIS_MAX
        )
    if isinstance(value, float):
        return EPOCH_SECONDS_MIN <= value <= EPOCH_SECONDS_MAX or (
            EPOCH_MILLIS_MIN <= value <= EPOCH_MILLIS_MAX
        )
    if isinstance(value, str) and value.isdigit():
        return looks_like_epoch(int(value))
    return False


def is_temp_path(text: str) -> bool:
    """True only for strings that look like paths into known temp roots."""
    if not text or not ("/" in text or "\\" in text):
        return False
    lowered = text.lower()
    try:
        tempdir = str(Path(tempfile.gettempdir()).resolve()).lower().rstrip("\\/")
    except Exception:  # pragma: no cover - gettempdir never fails in practice
        tempdir = None
    if tempdir and lowered.startswith(tempdir):
        return True
    return any(marker in lowered for marker in _TEMP_ROOTS)


def strip_ansi(text: str) -> str:
    text = ANSI_OSC_RE.sub("", text)
    return ANSI_CSI_RE.sub("", text)


def normalize_lines(text: str) -> str:
    """Unify line endings and strip trailing whitespace per line."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines)
