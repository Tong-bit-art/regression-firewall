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


def test_canonical_signature_deterministic_across_subprocesses():
    """P0 fix: framework-generated callables must produce the same canonical
    fingerprint across subprocess invocations. Uses a synthetic class with
    volatile default reprs (simulating typer.Typer's Doc() issue) so it runs
    anywhere without typer installed."""
    import subprocess
    import textwrap

    helper_script = textwrap.dedent("""\
        import sys
        sys.path.insert(0, r"D:\\Regression Firewall Skill")
        from regression_firewall.capture._api_runner import _canonical_signature

        class _Volatile:
            def __repr__(self):
                return f"<Volatile {id(self)}>"
        _volatile = _Volatile()

        class FrameworkCallable:
            def __init__(self, name="app", *, debug=_volatile, rich=True):
                pass

        print(_canonical_signature(FrameworkCallable))
    """)
    import tempfile
    script_file = Path(tempfile.mkdtemp()) / "sig_test.py"
    script_file.write_text(helper_script, encoding="utf-8")

    sigs = set()
    for _ in range(3):
        proc = subprocess.run(
            [sys.executable, "-c", script_file.read_text(encoding="utf-8")],
            capture_output=True, text=True, timeout=30, cwd=str(tmp_path),
        )
        assert proc.returncode == 0, proc.stderr
        sigs.add(proc.stdout.strip())
    assert len(sigs) == 1, f"nondeterministic: {sigs}"


def test_canonical_signature_detects_real_changes():
    """The canonical fingerprint must still detect real signature changes."""
    import sys
    sys.path.insert(0, r"D:\Regression Firewall Skill")
    from regression_firewall.capture._api_runner import _canonical_signature

    def func_before(a, b=1, *, c="x"):
        pass

    def func_after(a, b, *, c="x", d=None):
        pass

    sig_before = _canonical_signature(func_before)
    sig_after = _canonical_signature(func_after)
    assert sig_before != sig_after, "real signature change not detected"
    # `b` went from having a default to not having one → structural change
    assert "=" in sig_before and "=" not in sig_after.split(",")[1]
    # `d` was added as a keyword param with a default
    assert "d=" in sig_after
