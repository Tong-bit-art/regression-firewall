"""End-to-end: `check --select` captures only surfaces whose mapped
dependencies intersect the changed-file set — and never skips silently."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from regression_firewall import cli

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")

CONFIG = """\
version: 1
surfaces:
  http: {enabled: false}
  public_api: {enabled: false}
  js_api: {enabled: false}
  cli:
    probes:
      - id: jobs
        command: ["python", "jobs/build.py"]
      - id: reports
        command: ["python", "reports/gen.py"]
"""


def _init_repo(tmp_path: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), check=True)
    (tmp_path / "jobs").mkdir(exist_ok=True)
    (tmp_path / "reports").mkdir(exist_ok=True)
    (tmp_path / "jobs" / "build.py").write_text("print('building')\n", encoding="utf-8")
    (tmp_path / "reports" / "gen.py").write_text("print('reporting')\n", encoding="utf-8")
    (tmp_path / ".regression-firewall.yml").write_text(CONFIG, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=str(tmp_path), check=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(tmp_path),
                          capture_output=True, text=True).stdout.strip()


@needs_git
def test_select_skips_untouched_surface_and_records_it(tmp_path):
    base = _init_repo(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0

    # change only the reports script (committed)
    (tmp_path / "reports" / "gen.py").write_text("print('reporting v2')\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "edit reports"], cwd=str(tmp_path), check=True)

    exit_code = cli.main(["--project", str(tmp_path), "check", "--select"])
    # the changed probe (reports) MUST run and catch its own stdout change
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    assert set(report["selection"]) == {"cli"}
    assert set(report["selection"]["cli"]) == {"jobs"}
    assert "intersect" in report["selection"]["cli"]["jobs"]
    # the changed probe ran and reported
    assert any(c["target"] == "reports" and c["category"] == "stdout_changed"
               for c in report["changes"])
    markdown = (tmp_path / ".regression-firewall" / "report.md").read_text(encoding="utf-8")
    assert "## Selective Capture" in markdown


@needs_git
def test_select_runs_surface_when_its_own_file_changes(tmp_path):
    base = _init_repo(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    (tmp_path / "jobs" / "build.py").write_text("print('building v2')\n", encoding="utf-8")

    exit_code = cli.main(["--project", str(tmp_path), "check", "--select"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    assert set(report["selection"]) == {"cli"}
    assert set(report["selection"]["cli"]) == {"reports"}
    assert any(c["target"] == "jobs" for c in report["changes"])


@needs_git
def test_full_check_without_select_ignores_nothing(tmp_path):
    _init_repo(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    # dirty (uncommitted) change in jobs only
    (tmp_path / "jobs" / "build.py").write_text("print('building v2')\n", encoding="utf-8")

    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    assert report["selection"] == {}
    # both probes ran; only the touched one has changes
    assert any(c["target"] == "jobs" for c in report["changes"])
    assert not any(c["target"] == "reports" for c in report["changes"])


@needs_git
def test_select_everything_skipped_never_passes(tmp_path):
    _init_repo(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    # change an unrelated file only
    (tmp_path / "docs.md").write_text("# docs\n", encoding="utf-8")

    exit_code = cli.main(["--project", str(tmp_path), "check", "--select"])
    assert exit_code == cli.EXIT_REVIEW  # nothing verified -> cannot be PASS
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    assert set(report["selection"]) == {"cli"}
    assert set(report["selection"]["cli"]) == {"jobs", "reports"}
    assert any("nothing was verified" in w for w in report["warnings"])


@needs_git
def test_select_clean_change_passes(tmp_path):
    _init_repo(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    # touch the tracked file WITHOUT changing behavior (comment only)
    (tmp_path / "jobs" / "build.py").write_text("# touched\nprint('building')\n", encoding="utf-8")

    exit_code = cli.main(["--project", str(tmp_path), "check", "--select"])
    assert exit_code == cli.EXIT_OK
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    # the touched probe ran (clean); the untouched one was skipped
    assert set(report["selection"]) == {"cli"}
    assert set(report["selection"]["cli"]) == {"reports"}
    assert not any(c["target"] == "reports" for c in report["changes"])
