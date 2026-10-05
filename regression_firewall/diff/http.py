from __future__ import annotations

import fnmatch

from ..config.schema import Config
from ..models.change import MISSING
from ..models.snapshot import ProbeCapture
from ..normalize.engine import Normalizer
from .engine import diff_json


def _json_path_ignored(path: str, config: Config | None) -> bool:
    """ignore.json_paths suppresses ALL reported changes at matching JSON
    paths (the change path is compared without the leading ``$.``)."""
    if config is None or not config.ignore.json_paths:
        return False
    plain = path[2:] if path.startswith("$.") else path
    return any(fnmatch.fnmatchcase(plain, pattern) for pattern in config.ignore.json_paths)


def diff_http(before: ProbeCapture, after: ProbeCapture, normalizer: Normalizer,
              config: Config, make_change) -> list:
    changes = []

    if before.ok != after.ok:
        changes.append(make_change(
            "http", after.target, "capture_error",
            before=before.error or "captured ok",
            after=after.error or "captured ok",
            description=(f"{after.target}: probe was {'failing' if not before.ok else 'working'} "
                         f"at baseline and is now {'failing' if not after.ok else 'working'}"),
            config=config,
        ))
        return changes

    bd, ad = before.data or {}, after.data or {}

    if bd.get("status") != ad.get("status"):
        status_before, status_after = bd.get("status"), ad.get("status")
        transition = _transition(status_before, status_after)
        severity = "high" if ("error" in (transition[0], transition[1])) else "medium"
        changes.append(make_change(
            "http", after.target, "status_changed",
            before=status_before, after=status_after,
            evidence={"transition": f"{transition[0]} -> {transition[1]}"},
            description=f"{after.target}: status {status_before} -> {status_after}",
            severity=severity, config=config,
        ))

    ct_before = (bd.get("headers") or {}).get("content-type")
    ct_after = (ad.get("headers") or {}).get("content-type")
    if ct_before != ct_after:
        changes.append(make_change(
            "http", after.target, "content_type_changed",
            before=ct_before, after=ct_after,
            description=(f"{after.target}: content-type "
                         f"{ct_before or '<absent>'} -> {ct_after or '<absent>'}"),
            config=config,
        ))

    headers_before = normalizer.normalize_headers(bd.get("headers") or {})
    headers_after = normalizer.normalize_headers(ad.get("headers") or {})
    for name in sorted(set(headers_before) | set(headers_after)):
        if name == "content-type":
            continue  # reported as content_type_changed above
        value_before = headers_before.get(name, MISSING)
        value_after = headers_after.get(name, MISSING)
        if value_before != value_after:
            changes.append(make_change(
                "http", after.target, "header_changed", path=name,
                before=value_before, after=value_after,
                description=(f"{after.target}: header '{name}' "
                             f"{_show(value_before)} -> {_show(value_after)}"),
                config=config,
            ))

    cookies_before = normalizer.normalize_cookies(bd.get("cookies") or {})
    cookies_after = normalizer.normalize_cookies(ad.get("cookies") or {})
    for name in sorted(set(cookies_before) | set(cookies_after)):
        value_before = cookies_before.get(name, MISSING)
        value_after = cookies_after.get(name, MISSING)
        if value_before != value_after:
            changes.append(make_change(
                "http", after.target, "cookie_changed", path=name,
                before=value_before, after=value_after,
                description=(f"{after.target}: cookie '{name}' "
                             f"{_show(value_before)} -> {_show(value_after)}"),
                config=config,
            ))

    kind_before, kind_after = bd.get("body_kind"), ad.get("body_kind")
    body_before, body_after = bd.get("body"), ad.get("body")
    if kind_before != kind_after:
        # A content-type change already explains the payload flip; only emit a
        # separate shape change when the content-type did not change.
        if ct_before == ct_after:
            changes.append(make_change(
                "http", after.target, "response_shape_changed",
                before={"body_kind": kind_before}, after={"body_kind": kind_after},
                description=(f"{after.target}: response body kind "
                             f"{kind_before} -> {kind_after}"),
                config=config,
            ))
    elif kind_before == "json" and body_before is not None and body_after is not None:
        normalized_before = normalizer.normalize_json(body_before)
        normalized_after = normalizer.normalize_json(body_after)
        for entry in diff_json(normalized_before, normalized_after):
            if _json_path_ignored(entry["path"], config):
                continue
            changes.append(make_change(
                "http", after.target, entry,
                evidence={"json_path": entry["path"]},
                description=(f"{after.target}: {entry['category'].replace('_', ' ')} "
                             f"at {entry['path']}"),
                config=config,
            ))
    elif kind_before == "binary" and kind_after == "binary":
        size_before = (body_before or {}).get("size") if isinstance(body_before, dict) else None
        size_after = (body_after or {}).get("size") if isinstance(body_after, dict) else None
        if size_before != size_after:
            changes.append(make_change(
                "http", after.target, "value_changed", path="$body",
                before={"size": size_before}, after={"size": size_after},
                description=f"{after.target}: binary response body changed "
                            f"({size_before} -> {size_after} bytes)",
                config=config,
            ))
    elif kind_before == "text" and kind_after == "text":
        text_before = normalizer.normalize_text(str(body_before or ""))
        text_after = normalizer.normalize_text(str(body_after or ""))
        if text_before != text_after:
            changes.append(make_change(
                "http", after.target, "value_changed", path="$body",
                before=_preview(body_before), after=_preview(body_after),
                description=f"{after.target}: response body text changed",
                config=config,
            ))

    return changes


def _transition(status_before, status_after) -> tuple:
    def klass(status):
        if status is None:
            return "none"
        if 200 <= status < 300:
            return "success"
        if 300 <= status < 400:
            return "redirect"
        if 400 <= status < 600:
            return "error"
        return "info"

    return klass(status_before), klass(status_after)


def _show(value) -> str:
    if value is MISSING or value is None:
        return "<absent>"
    text = str(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _preview(value) -> str:
    text = str(value or "")
    return text if len(text) <= 200 else text[:197] + "..."
