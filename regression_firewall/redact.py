"""Capture-time secret redaction.

Snapshots are plain JSON files on disk and are routinely attached to bug
reports; normalization only protects diffs and reports, so anything that
reaches a response must be masked BEFORE it is stored. Off-switch:
``redaction.secrets: false`` (config changes still trip the config-hash
warning on the next check).
"""

from __future__ import annotations

from .normalize import rules as R

REDACTED = "<REDACTED>"

# Headers whose mere value is a credential.
SECRET_HEADERS = {"authorization", "proxy-authorization", "www-authenticate", "cookie"}


def redact_headers(headers: dict, enabled: bool = True) -> dict:
    if not enabled:
        return headers
    out = {}
    for name, value in headers.items():
        low = str(name).lower()
        out[name] = REDACTED if (low in SECRET_HEADERS or R.TOKEN_KEY_RE.search(low)) else value
    return out


def redact_cookies(cookies: dict, enabled: bool = True) -> dict:
    if not enabled:
        return cookies
    # Blanket by default: a cookie value is session state even when the name
    # looks innocent ("prefs" has carried JWTs before). Presence and name
    # changes remain detectable; value-level detection needs the off-switch.
    return {name: REDACTED for name in cookies}


def redact_json(value, key=None, enabled: bool = True):
    if not enabled:
        return value
    if isinstance(value, dict):
        return {k: redact_json(v, key=k, enabled=True) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_json(v, key=key, enabled=True) for v in value]
    if key is not None and R.TOKEN_KEY_RE.search(str(key)):
        return REDACTED
    return value
