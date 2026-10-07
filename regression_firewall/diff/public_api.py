from __future__ import annotations

from ..config.schema import Config
from ..models.snapshot import ProbeCapture


def _resolvable(entry) -> bool:
    """False when a symbol entry exists but introspection could not resolve
    it (stale ``__all__`` entry, broken export, getattr failure)."""
    return bool(entry) and entry.get("kind") != "error"


def diff_public_api(before: ProbeCapture, after: ProbeCapture,
                    config: Config, make_change) -> list:
    changes = []

    if before.ok != after.ok:
        changes.append(make_change(
            "public_api", after.target, "capture_error",
            before=before.error or "introspected ok",
            after=after.error or "introspected ok",
            description=(f"{after.target}: module was {'importable' if before.ok else 'broken'} "
                         f"at baseline and is now {'importable' if after.ok else 'broken'}"),
            config=config,
        ))
        return changes

    module = (after.data or {}).get("module") or after.target
    symbols_before = (before.data or {}).get("symbols") or {}
    symbols_after = (after.data or {}).get("symbols") or {}

    for name in sorted(set(symbols_before) | set(symbols_after)):
        entry_before = symbols_before.get(name)
        entry_after = symbols_after.get(name)
        resolvable_before = _resolvable(entry_before)
        resolvable_after = _resolvable(entry_after)

        if resolvable_before and not resolvable_after:
            changes.append(make_change(
                "public_api", f"{module}.{name}", "symbol_removed",
                before={"kind": entry_before.get("kind"),
                        "signature": entry_before.get("signature")},
                after=None,
                description=(f"{module}.{name} ({entry_before.get('kind')}) "
                             f"is no longer importable"),
                config=config,
            ))
        elif not resolvable_before and resolvable_after:
            changes.append(make_change(
                "public_api", f"{module}.{name}", "symbol_added",
                before=None,
                after={"kind": entry_after.get("kind"),
                       "signature": entry_after.get("signature")},
                description=f"{module}.{name} ({entry_after.get('kind')}) is newly importable",
                config=config,
            ))
        elif resolvable_before and resolvable_after:
            sig_before, sig_after = entry_before.get("signature"), entry_after.get("signature")
            if sig_before != sig_after and sig_before and sig_after:
                changes.append(make_change(
                    "public_api", f"{module}.{name}", "signature_changed",
                    before=sig_before, after=sig_after,
                    evidence={"kind": entry_after.get("kind")},
                    description=(f"{module}.{name}: signature {sig_before} -> {sig_after}"),
                    config=config,
                ))

    for name in sorted(set((before.data or {}).get("submodules") or [])
                       - set((after.data or {}).get("submodules") or [])):
        changes.append(make_change(
            "public_api", name, "symbol_removed",
            before={"kind": "module"}, after=None,
            description=f"submodule {name} is no longer importable",
            config=config,
        ))

    for name in sorted(set((after.data or {}).get("submodules") or [])
                       - set((before.data or {}).get("submodules") or [])):
        changes.append(make_change(
            "public_api", name, "symbol_added",
            before=None, after={"kind": "module"},
            description=f"submodule {name} is new",
            config=config,
        ))

    exports_before = (before.data or {}).get("exports")
    exports_after = (after.data or {}).get("exports")
    if exports_before is not None and exports_after is not None and exports_before != exports_after:
        removed = sorted(set(exports_before) - set(exports_after))
        added = sorted(set(exports_after) - set(exports_before))
        changes.append(make_change(
            "public_api", module, "export_changed",
            before=exports_before, after=exports_after,
            evidence={"removed": removed, "added": added},
            description=(f"{module}: __all__ changed "
                         f"(-{removed or 'nothing'}, +{added or 'nothing'})"),
            config=config,
        ))

    return changes
