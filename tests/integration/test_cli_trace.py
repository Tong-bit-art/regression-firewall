"""End-to-end CLI probe behavior tracing (trace.fs_writes / trace.env_reads).

Tracing works only for Python commands (sitecustomize injection) — that
limitation is part of the contract being tested."""

import json

from regression_firewall import cli

JOB = """\\
import os
from pathlib import Path

token = os.getenv("APP_TOKEN")
out = Path("out")
out.mkdir(exist_ok=True)
(out / "receipt.json").write_text(f"token={token}")
print("done")
"""


def _project(tmp_path, trace_config):
    (tmp_path / "job.py").write_text(JOB, encoding="utf-8")
    (tmp_path / ".regression-firewall.yml").write_text(
        "version: 1\n"
        "surfaces:\n"
        "  http: {enabled: false}\n"
        "  public_api: {enabled: false}\n"
        "  js_api: {enabled: false}\n"
        "  cli:\n"
        "    probes:\n"
        "      - id: job\n"
        "        command: ['python', 'job.py']\n"
        f"        trace:\n{trace_config}\n",
        encoding="utf-8",
    )


def test_trace_records_writes_and_env_names(tmp_path):
    _project(tmp_path, "          fs_writes: true\n          env_reads: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    snapshot = json.loads(
        (tmp_path / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    data = snapshot["surfaces"]["cli"][0]["data"]
    assert "fs_writes" in data and "env_reads" in data
    # env var NAMES are recorded, never values
    assert "APP_TOKEN" in data["env_reads"]
    assert "secret-value" not in json.dumps(snapshot)
    assert any(p.endswith("receipt.json") for p in data["fs_writes"])
    # the mkdir'd directory itself is a write target too
    assert any(p.endswith("out") for p in data["fs_writes"])


def test_new_write_target_detected(tmp_path):
    _project(tmp_path, "          fs_writes: true\n          env_reads: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    job = tmp_path / "job.py"
    job.write_text(JOB + '(out / "extra.log").write_text("more")\n', encoding="utf-8")
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    added = [c for c in report["changes"] if c["category"] == "fs_write_added"]
    assert len(added) == 1
    assert added[0]["classification"] == "uncertain"
    assert added[0]["severity"] == "medium"
    assert added[0]["path"].endswith("extra.log")


def test_new_env_dependency_detected(tmp_path):
    _project(tmp_path, "          fs_writes: false\n          env_reads: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    job = tmp_path / "job.py"
    job.write_text(JOB + 'region = os.environ.get("APP_REGION", "x")\nprint(region)\n',
                   encoding="utf-8")
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    added = [c for c in report["changes"] if c["category"] == "env_read_added"]
    assert len(added) == 1
    assert added[0]["path"] == "APP_REGION"


def test_identical_behavior_traces_clean(tmp_path):
    _project(tmp_path, "          fs_writes: true\n          env_reads: true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_OK


def test_trace_skipped_for_non_python_command(tmp_path):
    """A non-Python command still runs (and fails here, since the binary does
    not exist) but tracing is skipped with a warning, not an error."""
    (tmp_path / "job.py").write_text(JOB, encoding="utf-8")
    (tmp_path / ".regression-firewall.yml").write_text(
        "version: 1\n"
        "surfaces:\n"
        "  http: {enabled: false}\n"
        "  public_api: {enabled: false}\n"
        "  js_api: {enabled: false}\n"
        "  cli:\n"
        "    probes:\n"
        "      - id: listing\n"
        "        command: ['definitely-not-a-real-binary']\n"
        "        trace: true\n",
        encoding="utf-8",
    )
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    snapshot = json.loads(
        (tmp_path / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    capture = snapshot["surfaces"]["cli"][0]
    assert capture["ok"] is False  # the command itself does not exist
    assert "fs_writes" not in (capture.get("data") or {})
