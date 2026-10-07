"""Regression test for the real-world benchmark finding: the api-runner runs
in script mode with sys.path[0] = the capture package directory. A module
named http.py there shadowed the stdlib `http` package and made every
public-API capture fail on real projects (urllib3 imports http.client)."""

import json
import subprocess
import sys
from pathlib import Path

from regression_firewall.capture import public_api as api_capture


def test_api_runner_does_not_shadow_stdlib_http(tmp_path):
    runner = Path(api_capture.__file__).with_name("_api_runner.py")
    out = tmp_path / "out.json"
    # importing http.client exercises exactly the shadowing path urllib3 hits
    proc = subprocess.run(
        [sys.executable, str(runner), "--module", "http.client", "--out", str(out)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True, payload["error"]
    assert "HTTPConnection" in payload["symbols"]


def test_api_runner_module_import_uses_isolated_cwd(tmp_path):
    """A cwd containing shadowing files must not break introspection: the
    runner resolves the target module through PYTHONPATH, not cwd tricks."""
    (tmp_path / "http.py").write_text("# shadow attempt\n", encoding="utf-8")
    (tmp_path / "mymodule.py").write_text("BENCHMARK_CONST = 1\n", encoding="utf-8")
    out = tmp_path / "out.json"
    proc = subprocess.run(
        [sys.executable, str(api_capture.RUNNER_PATH), "--module", "mymodule",
         "--out", str(out)],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=60,
        env={"SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""),
             "PATH": __import__("os").environ.get("PATH", ""),
             "PYTHONPATH": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True, payload["error"]
    assert payload["symbols"]["BENCHMARK_CONST"]["kind"] == "int"
