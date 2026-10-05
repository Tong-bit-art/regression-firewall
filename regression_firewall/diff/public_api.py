from __future__ import annotations

from ..config.schema import Config
from ..models.snapshot import ProbeCapture


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

    for name in sorted(set(symbols_before) - set(symbols_after)):
        entry = symbols_before[name]
        changes.append(make_change(
            "public_api", f"{module}.{name}", "symbol_removed",
            before={"kind": entry.get("kind"), "signature": entry.get("signature")},
            after=None,
            description=(f"{module}.{name} ({entry.get('kind')}) is no longer importable"),
            config=config,
        ))

    for name in sorted(set(symbols_after) - set(symbols_before)):
        entry = symbols_after[name]
        changes.append(make_change(
            "public_api", f"{module}.{name}", "symbol_added",
            before=None,
            after={"kind": entry.get("kind"), "signature": entry.get("signature")},
            description=f"{module}.{name} ({entry.get('kind')}) is newly importable",
            config=config,
        ))

    for name in sorted(set(symbols_before) & set(symbols_after)):
        entry_before, entry_after = symbols_before[name], symbols_after[name]
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
