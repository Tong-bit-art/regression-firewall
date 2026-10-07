from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ..config.schema import ApiSurfaceConfig
from ..models.snapshot import ProbeCapture

RUNNER_PATH = Path(__file__).with_name("_api_runner.py")
RUNNER_TIMEOUT = 60.0


def capture_api_probes(cfg: ApiSurfaceConfig, project_root: Path) -> tuple:
    warnings: list = []
    captures = []
    for probe in cfg.probes:
        capture, warning = _run_probe(probe, project_root)
        captures.append(capture)
        if warning:
            warnings.append(warning)
    return captures, warnings


def _run_probe(probe, project_root: Path) -> tuple:
    handle = tempfile.NamedTemporaryFile(prefix="regfw-api-", suffix=".json", delete=False)
    handle.close()
    out_path = Path(handle.name)

    env = os.environ.copy()
    # Standard layout support: flat projects expose the package at the
    # project root, src-layout projects at <root>/src. Both roots are the
    # project's own code; adding them keeps introsption on the working tree
    # instead of an installed copy.
    import_roots = [str(project_root)]
    src_root = Path(project_root) / "src"
    if src_root.is_dir():
        import_roots.append(str(src_root))
    env["PYTHONPATH"] = os.pathsep.join(
        import_roots + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    command = [sys.executable, str(RUNNER_PATH), "--module", probe.module, "--out", str(out_path)]
    if probe.include_private:
        command.append("--include-private")

    try:
        completed = subprocess.run(
            command,
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=RUNNER_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        _cleanup(out_path)
        return (
            ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                         error=f"introspection timed out after {RUNNER_TIMEOUT:g}s"),
            None,
        )
    except OSError as exc:
        _cleanup(out_path)
        return (
            ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                         error=f"could not start introspection subprocess: {exc}"),
            None,
        )

    import json

    try:
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _cleanup(out_path)
        stderr_tail = (completed.stderr or "")[-400:].strip()
        return (
            ProbeCapture(
                probe_id=probe.id, target=probe.id, ok=False,
                error=f"introspection failed (exit {completed.returncode}): {stderr_tail}",
            ),
            None,
        )
    _cleanup(out_path)

    if not payload.get("ok"):
        return (
            ProbeCapture(probe_id=probe.id, target=probe.id, ok=False,
                         error=payload.get("error") or "unknown introspection error"),
            None,
        )

    return (
        ProbeCapture(
            probe_id=probe.id,
            target=probe.id,
            ok=True,
            data={
                "module": payload.get("module"),
                "symbols": payload.get("symbols") or {},
                "submodules": payload.get("submodules") or [],
                "exports": payload.get("exports"),
            },
        ),
        None,
    )


def _cleanup(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
