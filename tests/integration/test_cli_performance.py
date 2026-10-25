"""End-to-end: probe.performance — opt-in runtime measurement with median
ratio budgets."""

import json
import sys

from regression_firewall import cli


def _project(tmp_path, sleep_seconds, perf_config):
    (tmp_path / "job.py").write_text(
        f"import time\n"
        f"time.sleep({sleep_seconds})\n"
        f"print('done')\n",
        encoding="utf-8",
    )
    (tmp_path / ".regression-firewall.yml").write_text(
        "version: 1\n"
        "surfaces:\n"
        "  http: {enabled: false}\n"
        "  public_api: {enabled: false}\n"
        "  js_api: {enabled: false}\n"
        "  cli:\n"
        "    probes:\n"
        "      - id: job\n"
        f"        command: ['{sys.executable}', 'job.py']\n"
        "        performance:\n" + perf_config + "\n",
        encoding="utf-8",
    )


def test_same_runtime_is_clean_and_records_median(tmp_path):
    _project(tmp_path, 0.02, "          enabled: true\n          repeat: 3\n          warmup: 1")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_OK
    snapshot = json.loads(
        (tmp_path / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    data = snapshot["surfaces"]["cli"][0]["data"]
    assert data["runtime_runs"] == 3
    assert data["runtime_ms"] == sorted(data["runtime_ms"])
    assert data["runtime_median_ms"] >= 15  # a 20ms sleep cannot be faster


def test_large_slowdown_is_detected(tmp_path):
    _project(tmp_path, 0.02, "          enabled: true\n          repeat: 3\n          warmup: 1\n          max_ratio: 2.0")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    (tmp_path / "job.py").write_text(
        "import time\ntime.sleep(0.5)\nprint('done')\n", encoding="utf-8"
    )
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    regressions = [c for c in report["changes"] if c["category"] == "runtime_regressed"]
    assert len(regressions) == 1
    change = regressions[0]
    assert change["classification"] == "uncertain"
    assert change["severity"] == "medium"
    assert change["evidence"]["ratio"] > 2.0
    assert change["before"]["median_ms"] >= 15
    assert change["after"]["median_ms"] >= 400


def test_default_off_without_performance_section(tmp_path):
    (tmp_path / "job.py").write_text("print('done')\n", encoding="utf-8")
    (tmp_path / ".regression-firewall.yml").write_text(
        "version: 1\n"
        "surfaces:\n"
        "  http: {enabled: false}\n"
        "  public_api: {enabled: false}\n"
        "  js_api: {enabled: false}\n"
        "  cli:\n"
        "    probes:\n"
        "      - id: job\n"
        f"        command: ['{sys.executable}', 'job.py']\n",
        encoding="utf-8",
    )
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    snapshot = json.loads(
        (tmp_path / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    data = snapshot["surfaces"]["cli"][0]["data"]
    assert "runtime_median_ms" not in data
    assert cli.main(["--project", str(tmp_path), "check"]) == cli.EXIT_OK


def test_performance_true_shorthand(tmp_path):
    _project(tmp_path, 0.01, "          true")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    snapshot = json.loads(
        (tmp_path / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    data = snapshot["surfaces"]["cli"][0]["data"]
    assert data["runtime_runs"] == 5  # default repeat
