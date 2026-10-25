"""Static public-API capture for JavaScript/TypeScript entry files.

Nothing is executed: the probe reads the configured file and statically
extracts its public exports (js_exports.py). A missing file is a FAILED
capture (behavior evidence: the entry point is gone), not a config error.
"""

from __future__ import annotations

from pathlib import Path

from ..config.schema import JsApiSurfaceConfig
from ..models.snapshot import ProbeCapture
from ..js_exports import MAX_RESOLVE_DEPTH, collect_public_symbols


def capture_js_api_probes(cfg: JsApiSurfaceConfig, project_root: Path) -> tuple:
    captures, warnings = [], []
    for probe in cfg.probes:
        capture, probe_warnings = _capture_probe(probe, project_root)
        captures.append(capture)
        warnings.extend(probe_warnings)
    return captures, warnings


def _capture_probe(probe, project_root: Path) -> tuple:
    path = (project_root / probe.file).resolve()
    if not path.is_file():
        return ProbeCapture(
            probe_id=probe.id, target=probe.id, ok=False,
            error=f"entry file not found: {probe.file}",
        ), []

    resolved = collect_public_symbols(path, MAX_RESOLVE_DEPTH)
    warnings = [
        f"probe {probe.id!r}: re-export {spec!r} could not be resolved "
        "(relative specifier expected; aliases/packages are not followed)"
        for spec in sorted(set(resolved["unresolved"]))
    ]
    symbols = {}
    for name, entry in resolved["symbols"].items():
        origin = str(entry.get("origin") or "")
        try:
            origin = Path(origin).relative_to(project_root).as_posix()
        except ValueError:
            pass  # outside the project (unexpected); keep as-is
        symbols[name] = {
            "kind": entry.get("kind"),
            "signature": entry.get("signature"),
            "origin": origin,
        }
    return ProbeCapture(
        probe_id=probe.id,
        target=probe.id,
        ok=True,
        data={"file": probe.file, "symbols": symbols},
    ), warnings
