import json
import shutil
import subprocess
from pathlib import Path

import pytest

from regression_firewall import cli
from regression_firewall.provenance import (
    CHANGED_FILES_CAP,
    _porcelain_paths,
    collect_changed_files,
)

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def _init_repo(tmp_path: Path) -> str:
    """A committed repo with two files; returns the base commit."""
    _git(["init", "-q"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "test"], tmp_path)
    (tmp_path / "app.py").write_text("# v1\nprint('v1')\n", encoding="utf-8")
    (tmp_path / "lib.py").write_text("X = 1\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-q", "-m", "base"], tmp_path)
    return _git(["rev-parse", "HEAD"], tmp_path).stdout.strip()


# -- porcelain parsing ------------------------------------------------------------


def test_porcelain_paths_basic():
    out = "\n".join([
        " M app.py",
        "?? new_file.txt",
        "A  staged.py",
        "R  old_name.py -> renamed.py",
        'M  "quoted path.py"',
    ])
    assert _porcelain_paths(out) == [
        "app.py", "new_file.txt", "staged.py", "renamed.py", "quoted path.py",
    ]


def test_porcelain_paths_empty():
    assert _porcelain_paths("") == []


# -- collect_changed_files ---------------------------------------------------------


@needs_git
def test_no_base_commit_is_unavailable(tmp_path):
    info = collect_changed_files(tmp_path, None)
    assert info == {"available": False, "files": [], "truncated": False}


@needs_git
def test_committed_and_dirty_files_are_collected(tmp_path):
    base = _init_repo(tmp_path)

    (tmp_path / "app.py").write_text("print('v2')\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-q", "-m", "edit"], tmp_path)
    (tmp_path / "scratch.txt").write_text("dirty\n", encoding="utf-8")

    info = collect_changed_files(tmp_path, base, current_dirty=True)
    assert info["available"] is True
    assert info["files"] == ["app.py", "scratch.txt"]
    assert info["truncated"] is False


@needs_git
def test_no_changes_clean_tree(tmp_path):
    base = _init_repo(tmp_path)
    info = collect_changed_files(tmp_path, base, current_dirty=False)
    assert info["available"] is True
    assert info["files"] == []


@needs_git
def test_cap_truncates(tmp_path, monkeypatch):
    base = _init_repo(tmp_path)
    monkeypatch.setattr("regression_firewall.provenance.CHANGED_FILES_CAP", 1)
    (tmp_path / "app.py").write_text("print('v2')\n", encoding="utf-8")
    (tmp_path / "lib.py").write_text("X = 2\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-q", "-m", "edit two files"], tmp_path)
    info = collect_changed_files(tmp_path, base)
    assert info["files"] == ["app.py"]
    assert info["truncated"] is True


@needs_git
def test_dirty_false_ignores_working_tree(tmp_path):
    base = _init_repo(tmp_path)
    (tmp_path / "scratch.txt").write_text("dirty\n", encoding="utf-8")
    info = collect_changed_files(tmp_path, base, current_dirty=False)
    assert info["files"] == []


# -- end-to-end: the hint lands in the report -------------------------------------


CONFIG = """\
version: 1
surfaces:
  http: {enabled: false}
  public_api: {enabled: false}
  cli:
    probes:
      - id: run
        command: ["python", "app.py"]
"""


@needs_git
def test_check_report_contains_changed_files_hint(tmp_path):
    base = _init_repo(tmp_path)
    (tmp_path / ".regression-firewall.yml").write_text(CONFIG, encoding="utf-8")

    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0

    # a comment-only commit (no behavior change) plus a dirty untracked file
    (tmp_path / "app.py").write_text("# v2\nprint('v1')\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-q", "-m", "edit app"], tmp_path)
    (tmp_path / "notes.txt").write_text("dirty\n", encoding="utf-8")

    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_OK  # behavior unchanged: stdout identical

    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    assert report["changed_files"] == ["app.py", "notes.txt"]

    markdown = (tmp_path / ".regression-firewall" / "report.md").read_text(encoding="utf-8")
    assert "Changed Files (git hint)" in markdown
    assert "`app.py`" in markdown
