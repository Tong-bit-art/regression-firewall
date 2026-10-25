from __future__ import annotations

import fnmatch
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from ..config.schema import CliSurfaceConfig
from ..models.snapshot import ProbeCapture


def capture_cli_probes(cfg: CliSurfaceConfig, project_root: Path) -> tuple:
    captures, warnings = [], []
    for probe in cfg.probes:
        capture, probe_warnings = _run_probe(probe, project_root)
        captures.append(capture)
        warnings.extend(probe_warnings)
    return captures, warnings


def _run_probe(probe, project_root: Path) -> tuple:
    command = [_resolve_interpreter(part) for part in probe.command]
    cwd = (project_root / probe.cwd).resolve()
    env = os.environ.copy()
    env.update({k: str(v) for k, v in (probe.env or {}).items()})
    # Probe scripts may import modules; stale bytecode must never be captured.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    warnings = []
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            timeout=probe.timeout,
        )
    except subprocess.TimeoutExpired:
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"command timed out after {probe.timeout:g}s"), warnings
    except FileNotFoundError:
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"command not found: {command[0]}"), warnings
    except PermissionError:
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"command is not executable: {command[0]}"), warnings

    files = {}
    for rel_path in probe.files:
        files[rel_path] = _file_entry(project_root / rel_path)
    for watch in probe.dirs:
        entries, truncated = _watch_dir_entries(watch, project_root)
        files.update(entries)
        if truncated:
            warnings.append(
                f"probe {probe.id!r}: directory watch {watch.path!r} stopped at "
                f"max_files={watch.max_files}; files beyond the cap are NOT watched"
            )

    return ProbeCapture(
        probe_id=probe.id,
        target=probe.id,
        ok=True,
        data={
            "exit_code": completed.returncode,
            "stdout": completed.stdout.decode("utf-8", errors="replace"),
            "stderr": completed.stderr.decode("utf-8", errors="replace"),
            "files": files,
        },
    ), warnings


def _watch_dir_entries(watch, project_root: Path) -> tuple:
    """All regular files below the watched directory, keyed by a stable
    relative posix path. A missing directory contributes nothing: if it exists
    at baseline but not at check, every file reports as deleted; if it only
    exists at check, every file reports as created. Walk order is sorted, so
    truncation at max_files is deterministic too."""
    root = (project_root / watch.path).resolve()
    if not root.is_dir():
        return {}, False
    prefix = str(watch.path).replace("\\", "/").strip("/")
    out = {}
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if not _dir_ignored(d, _rel_posix(dirpath, root, d), watch.ignore)
        )
        for name in sorted(filenames):
            rel = _rel_posix(dirpath, root, name)
            if _dir_ignored(name, rel, watch.ignore):
                continue
            if count >= watch.max_files:
                return out, True
            key = f"{prefix}/{rel}" if prefix else rel
            out[key] = _file_entry(Path(dirpath) / name)
            count += 1
    return out, False


def _rel_posix(dirpath: str, root: Path, name: str) -> str:
    rel = Path(dirpath).joinpath(name).relative_to(root)
    return rel.as_posix()


def _dir_ignored(name: str, rel_path: str, ignore: list) -> bool:
    for glob in ignore:
        if fnmatch.fnmatch(name, glob) or fnmatch.fnmatchcase(rel_path, glob):
            return True
    return False


def _file_entry(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "sha256": None, "size": None}
    content = path.read_bytes()
    return {
        "exists": True,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }


def _resolve_interpreter(part: str) -> str:
    if part in ("python", "python3", "python.exe"):
        return sys.executable
    return part
