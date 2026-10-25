"""Selective regression analysis (V0.5): run only the probes a change can
plausibly affect.

Safety-first contract:

- Selection is OPT-IN per invocation (``check --select``); the default is
  to capture everything.
- The decision unit is the PROBE (each probe is an independent command /
  module / entry file), grouped under its surface in the report.
- Dependency mapping is CONSERVATIVE. ``None`` dependencies (unknown) mean
  the probe ALWAYS runs. A skipped probe is always recorded in the report
  with its reason — skipping is never silent.
- Only path-based reasoning is used (probe commands, watched paths, module
  /package directories, JS entry chains). There is no import-graph or AST
  reachability analysis yet: anything the mapping cannot see counts as
  "affected".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SURFACES = ("http", "cli", "public_api", "js_api")


@dataclass
class ProbeDecision:
    surface: str
    probe_id: str
    run: bool
    reason: str
    dependencies: list  # project-relative posix paths (files or dirs), sorted


def decide_probes(config, project_root: Path, changed_files: list) -> list:
    """One decision per configured probe. ``changed_files`` are
    project-relative posix paths (from the git hint)."""
    if not changed_files:
        decisions = []
        for surface in SURFACES:
            for probe in _probes(config, surface):
                decisions.append(ProbeDecision(
                    surface, probe.id, True,
                    "changed-file list unavailable; capturing to be safe", []))
        return decisions

    changed = _paths_under(project_root, changed_files)
    decisions = []
    for surface in SURFACES:
        for probe in _probes(config, surface):
            deps = probe_dependencies(surface, probe, config, project_root)
            dep_rel = sorted(str(d.relative_to(project_root)).replace("\\", "/")
                             for d in (deps or ()))
            if deps is None:
                decisions.append(ProbeDecision(
                    surface, probe.id, True,
                    "dependencies could not be mapped; capturing to be safe", []))
                continue
            touched = sorted({str(p.relative_to(project_root)).replace("\\", "/")
                              for p in changed if _under_any(p, deps)})
            if touched:
                shown = ", ".join(touched[:5]) + (f" (+{len(touched) - 5} more)"
                                                  if len(touched) > 5 else "")
                decisions.append(ProbeDecision(
                    surface, probe.id, True, f"changed files touch this probe: {shown}",
                    dep_rel))
            else:
                decisions.append(ProbeDecision(
                    surface, probe.id, False,
                    f"none of the {len(changed)} changed file(s) intersect this "
                    f"probe's {len(dep_rel)} tracked path(s)",
                    dep_rel))
    return decisions


def _probes(config, surface: str) -> list:
    section = getattr(config, surface, None)
    if not section or not section.enabled:
        return []
    return list(section.probes)


def probe_dependencies(surface: str, probe, config, project_root: Path):
    """Files/dirs (absolute Paths) this probe depends on, or None when the
    mapping is unknown (which forces the probe to run)."""
    project_root = Path(project_root)
    if surface == "cli":
        return _cli_probe_dependencies(probe, project_root)
    if surface == "http":
        return _http_dependencies(config.http, project_root)  # server is shared
    if surface == "public_api":
        module_dir = _module_dir(project_root, probe.module)
        return {module_dir} if module_dir else None
    if surface == "js_api":
        return _js_probe_dependencies(probe, project_root)
    return None


def _cli_probe_dependencies(probe, root: Path):
    deps: set = set()
    probe_cwd = (root / probe.cwd).resolve()
    command = [_resolve_python(p) for p in probe.command]
    for i, token in enumerate(command):
        candidate = probe_cwd / token
        if _looks_like_path(token) and candidate.exists():
            deps.add(candidate.resolve())
        elif token == "-m" and i + 1 < len(command):
            module_dir = _module_dir(probe_cwd, command[i + 1])
            if module_dir is None:
                return None  # module not resolvable -> must run
            deps.add(module_dir)
    for watched in probe.files:
        deps.add((root / watched).resolve())
    for watch in getattr(probe, "dirs", None) or []:
        deps.add((root / watch.path).resolve())
    return deps or None  # a probe with no mappable files -> must run


def _http_dependencies(cfg, root: Path):
    if not (cfg.server and cfg.server.command):
        return None  # external/unmanaged server: cannot map code deps
    deps: set = set()
    server_cwd = (root / cfg.server.cwd).resolve()
    for i, token in enumerate(cfg.server.command):
        candidate = server_cwd / _resolve_python(token)
        if _looks_like_path(token) and candidate.exists():
            deps.add(candidate.resolve())
        elif token == "-m" and i + 1 < len(cfg.server.command):
            module_dir = _module_dir(server_cwd, cfg.server.command[i + 1])
            if module_dir is None:
                return None
            deps.add(module_dir)
    if cfg.discover_app:
        module_dir = _module_dir(server_cwd, cfg.discover_app.partition(":")[0])
        if module_dir is None:
            return None
        deps.add(module_dir)
    return deps or None


def _js_probe_dependencies(probe, root: Path):
    from .js_exports import collect_public_symbols

    entry = (root / probe.file).resolve()
    if not entry.is_file():
        return None  # entry missing -> run (capture will report it)
    deps = {entry}
    resolved = collect_public_symbols(entry)
    for origin in {s.get("origin") for s in resolved["symbols"].values()}:
        if origin:
            origin_path = Path(origin)
            deps.add(origin_path if origin_path.is_absolute() else (root / origin))
    return deps


def _module_dir(base: Path, module: str):
    """Package directory or module file for a dotted module name, resolved
    against base (and base/src). None when nothing exists there."""
    parts = module.split(".")
    if not parts or not all(re.fullmatch(r"\w+", p) for p in parts):
        return None
    for prefix in (base, base / "src"):
        package = prefix.joinpath(*parts)
        if package.is_dir():
            return package.resolve()
        as_file = package.with_suffix(".py")
        if as_file.is_file():
            return as_file.resolve()
        # "pkg.sub.symbol" may name a symbol inside pkg/sub.py
        parent_pkg = prefix.joinpath(*parts[:-1])
        if len(parts) > 1 and parent_pkg.with_suffix(".py").is_file():
            return parent_pkg.with_suffix(".py").resolve()
    return None


def _looks_like_path(token: str) -> bool:
    return bool(token) and (("/" in token or "\\" in token or token.endswith(".py"))
                            and not token.startswith("-"))


def _resolve_python(token: str) -> str:
    return "python" if token in ("python", "python3", "python.exe") else token


def _paths_under(root: Path, files: list) -> set:
    out = set()
    for name in files:
        try:
            out.add((root / name).resolve())
        except OSError:  # pragma: no cover
            continue
    return out


def _under_any(path: Path, deps: set) -> bool:
    for dep in deps:
        try:
            path.relative_to(dep)
            return True
        except ValueError:
            continue
    return False
