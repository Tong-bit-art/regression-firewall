"""Diff for the js_api surface: static export sets of JS/TS entry files.

Categories mirror public_api: symbol_removed (critical), symbol_added
(info), signature_changed (medium), export_changed (medium, kind flips),
capture_error (entry file appeared/disappeared).
"""

from __future__ import annotations

from ..config.schema import Config
from ..models.snapshot import ProbeCapture


def diff_js_api(before: ProbeCapture, after: ProbeCapture,
                config: Config, make_change) -> list:
    changes = []

    if before.ok != after.ok:
        changes.append(make_change(
            "js_api", after.target, "capture_error",
            before=before.error or "parsed ok",
            after=after.error or "parsed ok",
            description=(f"{after.target}: entry file was {'present' if before.ok else 'missing'} "
                         f"at baseline and is now {'present' if after.ok else 'missing'}"),
            config=config,
        ))
        return changes

    file_label = (after.data or {}).get("file") or after.target
    symbols_before = (before.data or {}).get("symbols") or {}
    symbols_after = (after.data or {}).get("symbols") or {}

    for name in sorted(set(symbols_before) | set(symbols_after)):
        entry_before = symbols_before.get(name)
        entry_after = symbols_after.get(name)
        target = f"{file_label}:{name}"

        if entry_before is not None and entry_after is None:
            changes.append(make_change(
                "js_api", target, "symbol_removed",
                before=_brief(entry_before), after=None,
                description=(f"{target} ({entry_before.get('kind')}) is no longer exported"),
                config=config,
            ))
        elif entry_before is None and entry_after is not None:
            changes.append(make_change(
                "js_api", target, "symbol_added",
                before=None, after=_brief(entry_after),
                description=f"{target} ({entry_after.get('kind')}) is newly exported",
                config=config,
            ))
        else:
            sig_before = entry_before.get("signature")
            sig_after = entry_after.get("signature")
            kind_before = entry_before.get("kind")
            kind_after = entry_after.get("kind")
            if sig_before != sig_after and sig_before and sig_after:
                changes.append(make_change(
                    "js_api", target, "signature_changed",
                    before=sig_before, after=sig_after,
                    evidence={"kind": kind_after},
                    description=f"{target}: signature {sig_before} -> {sig_after}",
                    config=config,
                ))
            elif kind_before != kind_after:
                changes.append(make_change(
                    "js_api", target, "export_changed",
                    before={"kind": kind_before}, after={"kind": kind_after},
                    description=f"{target}: export kind {kind_before} -> {kind_after}",
                    config=config,
                ))

    return changes


def _brief(entry: dict) -> dict:
    return {"kind": entry.get("kind"), "signature": entry.get("signature"),
            "origin": entry.get("origin")}
