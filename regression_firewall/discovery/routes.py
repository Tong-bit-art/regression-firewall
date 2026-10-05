from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

RUNNER_PATH = Path(__file__).with_name("_route_runner.py")


def discover_routes(spec: str, project_root: Path) -> tuple:
    """Discover HTTP routes from a configured app (module:attr).

    Returns (routes, error). routes is a list of {methods, path}.
    """
    handle = tempfile.NamedTemporaryFile(prefix="regfw-routes-", suffix=".json", delete=False)
    handle.close()
    out_path = Path(handle.name)

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(project_root)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, str(RUNNER_PATH), "--spec", spec, "--out", str(out_path)]
    try:
        completed = subprocess.run(
            command, cwd=str(project_root), env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        _cleanup(out_path)
        return [], f"route discovery failed: {exc}"

    import json

    try:
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _cleanup(out_path)
        tail = (completed.stderr or "")[-300:].strip()
        return [], f"route discovery failed: {tail or 'no output'}"
    _cleanup(out_path)

    if not payload.get("ok"):
        return [], f"route discovery failed: {payload.get('error')}"
    return payload.get("routes") or [], None


def _cleanup(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
