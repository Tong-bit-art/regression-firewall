import subprocess
import sys
from pathlib import Path

import pytest


def _run_rf(args, cwd, expect_exit=None):
    """Run the regression-firewall CLI as a subprocess (hermetic, like agents do)."""
    proc = subprocess.run(
        [sys.executable, "-m", "regression_firewall"] + list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if expect_exit is not None:
        assert proc.returncode == expect_exit, (
            f"regression-firewall {' '.join(args)} exited {proc.returncode}, "
            f"expected {expect_exit}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


@pytest.fixture
def run_rf():
    return _run_rf


@pytest.fixture
def write():
    return _write


@pytest.fixture
def project(tmp_path):
    """An empty project directory."""
    return tmp_path
