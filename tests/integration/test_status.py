"""End-to-end: `regression-firewall status` — one-screen orientation."""

import json

from regression_firewall import cli

CONFIG = """\
version: 1
surfaces:
  http: {enabled: false}
  public_api: {enabled: false}
  js_api: {enabled: false}
  cli:
    probes:
      - id: job
        command: ["python", "job.py"]
"""


def _capsys_lines(capsys):
    return capsys.readouterr().out.splitlines()


def test_status_fresh_project(tmp_path, capsys):
    (tmp_path / "job.py").write_text("print(1)\n", encoding="utf-8")
    assert cli.main(["--project", str(tmp_path), "status"]) == 0
    out = "\n".join(_capsys_lines(capsys))
    assert "Config:  none" in out
    assert "Baseline: none" in out
    assert "Intent:  none" in out
    assert "Last check: none" in out


def test_status_after_init(tmp_path, capsys):
    (tmp_path / "job.py").write_text("print(1)\n", encoding="utf-8")
    assert cli.main(["--project", str(tmp_path), "init"]) == 0
    assert cli.main(["--project", str(tmp_path), "status"]) == 0
    out = "\n".join(_capsys_lines(capsys))
    assert "Config:  .regression-firewall.yml" in out
    assert "cli 0 probe(s)" in out  # the scaffolded template has empty probes
    assert "Baseline: none" in out


def test_status_full_lifecycle(tmp_path, capsys):
    (tmp_path / "job.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / ".regression-firewall.yml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / ".regression-firewall").mkdir()
    (tmp_path / ".regression-firewall" / "intent.json").write_text(
        json.dumps({
            "schema_version": 1,
            "task": "polish the output",
            "expected_changes": [
                {"surface": "cli", "target": "job", "category": "stdout_changed"},
            ],
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    assert cli.main(["--project", str(tmp_path), "check"]) == 0

    assert cli.main(["--project", str(tmp_path), "status"]) == 0
    out = "\n".join(_capsys_lines(capsys))
    assert "Baseline: captured" in out and "integrity OK" in out
    assert "Intent:  1 declared change(s) — polish the output" in out
    assert "Last check: PASS (score 0/100)" in out
    assert "Audit journal: 2 event(s)" in out


def test_status_reports_tampered_baseline(tmp_path, capsys):
    (tmp_path / "job.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / ".regression-firewall.yml").write_text(CONFIG, encoding="utf-8")
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    baseline_path = tmp_path / ".regression-firewall" / "baseline.json"
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    data["surfaces"]["cli"][0]["data"]["stdout"] = "TAMPERED"
    baseline_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    assert cli.main(["--project", str(tmp_path), "status"]) == 0
    out = "\n".join(_capsys_lines(capsys))
    assert "integrity MISMATCH" in out
