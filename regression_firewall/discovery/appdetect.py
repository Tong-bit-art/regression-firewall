"""Convention-based HTTP app detection: find FastAPI/Flask/Starlette app
instances in a project without importing anything.

Detection is STATIC (regex over source text) so it can never execute project
code; the chosen candidate is imported later by the route runner, exactly
like an explicitly configured `discover_app`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Directories never worth scanning for app instances.
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", ".env", "node_modules",
    "__pycache__", ".tox", ".nox", ".mypy_cache", ".pytest_cache",
    "build", "dist", ".eggs", "site-packages",
}

# (framework, class name) pairs, in priority order.
FRAMEWORK_CLASSES = (
    ("fastapi", "FastAPI"),
    ("flask", "Flask"),
    ("starlette", "Starlette"),
)

# Files that usually hold the app, best first.
PREFERRED_FILENAMES = ("app.py", "main.py", "wsgi.py", "asgi.py", "application.py")

_IMPORT_RE = re.compile(
    rf"^\s*(?:from\s+({'|'.join(fr for fr, _ in FRAMEWORK_CLASSES)})"
    rf"\s+import\s+.*|\s*import\s+({'|'.join(fr for fr, _ in FRAMEWORK_CLASSES)})\b)",
    re.M,
)
_INSTANCE_RE = re.compile(
    rf"^(\w+)\s*=\s*({'|'.join(cls for _, cls in FRAMEWORK_CLASSES)})\s*\(",
    re.M,
)

MAX_SCAN_FILES = 200
MAX_FILE_BYTES = 512_000


@dataclass
class AppCandidate:
    module: str  # dotted module path, e.g. "api.main"
    attr: str  # variable name, e.g. "app"
    framework: str  # fastapi | flask | starlette
    file: str  # project-relative posix path
    line: int  # 1-based line of the assignment

    @property
    def spec(self) -> str:
        return f"{self.module}:{self.attr}"

    @property
    def score(self) -> tuple:
        """Higher is better. Deterministic ranking."""
        filename = Path(self.file).name
        file_rank = (
            -PREFERRED_FILENAMES.index(filename)
            if filename in PREFERRED_FILENAMES else 0
        )
        framework_rank = (
            [fr for fr, _ in FRAMEWORK_CLASSES].index(self.framework)
        )
        depth_penalty = self.file.count("/")
        name_bonus = 1 if self.attr == "app" else 0
        return (file_rank, -framework_rank, -depth_penalty, name_bonus, self.file)


def detect_app_candidates(project_root: Path) -> list:
    """All plausible app instances, best first. Static scan only."""
    root = Path(project_root)
    candidates = []
    seen = set()
    scanned = 0
    for path in _candidate_files(root):
        if scanned >= MAX_SCAN_FILES:
            break
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > MAX_FILE_BYTES or not _IMPORT_RE.search(text):
            continue
        for match in _INSTANCE_RE.finditer(text):
            var, cls = match.group(1), match.group(2)
            framework = next(fr for fr, c in FRAMEWORK_CLASSES if c == cls)
            rel = path.relative_to(root).as_posix()
            key = (rel, var)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(AppCandidate(
                module=_path_to_module(path.relative_to(root)),
                attr=var,
                framework=framework,
                file=rel,
                line=text[:match.start()].count("\n") + 1,
            ))
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def _candidate_files(root: Path):
    """Root *.py files plus one directory level deep, skipping junk dirs.
    Deterministic order: files first (alphabetical), then subdirs (alphabetical)."""
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_dir(), p.name.lower()))
    except OSError:
        return
    subdir_files = []
    for entry in entries:
        if entry.is_file() and entry.suffix == ".py":
            yield entry
        elif entry.is_dir() and entry.name not in SKIP_DIRS and not entry.name.startswith("."):
            try:
                for sub in sorted(entry.glob("*.py"), key=lambda p: p.name.lower()):
                    subdir_files.append(sub)
            except OSError:
                continue
    yield from subdir_files


def _path_to_module(rel: Path) -> str:
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else rel.stem


PROBE_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

_PARAM_SEGMENT_RE = re.compile(r"\{[^{}]+\}|<[^<>]+>")


def split_routes(routes: list) -> tuple:
    """Split discovered routes into concrete (probeable) and parameterized.

    A route path containing {param} (FastAPI/Starlette) or <param> (Flask)
    cannot be probed without a concrete value.
    """
    concrete, parameterized = [], []
    for route in routes:
        path = str(route.get("path") or "")
        if _PARAM_SEGMENT_RE.search(path):
            parameterized.append(route)
        else:
            concrete.append(route)
    return concrete, parameterized


def probes_from_routes(routes: list) -> list:
    """Deterministic probe dicts from discovered routes (one per method)."""
    probes = []
    for route in routes:
        path = str(route.get("path") or "")
        for method in sorted(route.get("methods") or []):
            if method not in PROBE_METHODS:
                continue
            probes.append({"id": f"{method} {path}", "method": method, "path": path})
    probes.sort(key=lambda p: (p["path"], p["method"]))
    return probes
