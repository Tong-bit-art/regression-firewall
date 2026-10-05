from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from ..config.schema import CliSurfaceConfig
from ..models.snapshot import ProbeCapture


def capture_cli_probes(cfg: CliSurfaceConfig, project_root: Path) -> tuple:
    captures = [_run_probe(probe, project_root) for probe in cfg.probes]
    return captures, []


def _run_probe(probe, project_root: Path) -> ProbeCapture:
    command = [_resolve_interpreter(part) for part in probe.command]
    cwd = (project_root / probe.cwd).resolve()
    env = os.environ.copy()
    env.update({k: str(v) for k, v in (probe.env or {}).items()})
    # Probe scripts may import modules; stale bytecode must never be captured.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

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
                            error=f"command timed out after {probe.timeout:g}s")
    except FileNotFoundError:
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"command not found: {command[0]}")
    except PermissionError:
        return ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                            error=f"command is not executable: {command[0]}")

    files = {}
    for rel_path in probe.files:
        files[rel_path] = _file_entry(project_root / rel_path)

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
    )


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
