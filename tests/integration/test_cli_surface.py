import json

from _fixtures import (
    CLI_CONFIG,
    DEPLOY_FAIL,
    DEPLOY_PLAIN,
    DEPLOY_WITH_RECEIPT,
    DEPLOY_WITH_RECEIPT_V2,
    read_report,
)


def test_full_loop_exit_code_regression(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)

    run_rf(["baseline"], project, expect_exit=0)
    write(project / "deploy.py", DEPLOY_FAIL)
    proc = run_rf(["check"], project)

    assert proc.returncode == 3, proc.stdout  # BLOCK
    report = read_report(project)
    assert report["verdict"] == "BLOCK"
    categories = {(c["category"], c["classification"]) for c in report["changes"]}
    assert ("exit_code_changed", "unexpected") in categories
    assert ("stdout_changed", "uncertain") in categories


def test_no_change_passes(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    proc = run_rf(["check"], project)
    assert proc.returncode == 0, proc.stdout
    report = read_report(project)
    assert report["verdict"] == "PASS"
    assert report["changes"] == []


def test_generated_file_created(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    write(project / "deploy.py", DEPLOY_WITH_RECEIPT)
    proc = run_rf(["check"], project)
    assert proc.returncode == 1, proc.stdout  # REVIEW: medium uncertain change
    report = read_report(project)
    assert ("file_created", "uncertain") in {
        (c["category"], c["classification"]) for c in report["changes"]
    }


def test_generated_file_modified(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_WITH_RECEIPT)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    write(project / "deploy.py", DEPLOY_WITH_RECEIPT_V2)
    proc = run_rf(["check"], project)
    assert proc.returncode == 1, proc.stdout
    report = read_report(project)
    assert ("file_modified", "uncertain") in {
        (c["category"], c["classification"]) for c in report["changes"]
    }


def test_check_requires_baseline(project, run_rf, write):
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    proc = run_rf(["check"], project)
    assert proc.returncode == 70
    assert "baseline" in proc.stderr


def test_init_scaffolds_config(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    proc = run_rf(["init"], project)
    assert proc.returncode == 0
    assert (project / ".regression-firewall.yml").is_file()
    assert (project / ".regression-firewall").is_dir()
    assert ".regression-firewall/" in (project / ".gitignore").read_text(encoding="utf-8")
    # second init without --force refuses
    proc = run_rf(["init"], project)
    assert proc.returncode == 70
    # with --force overwrites
    proc = run_rf(["init", "--force"], project)
    assert proc.returncode == 0


def test_config_change_warning(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    write(project / ".regression-firewall.yml",
          CLI_CONFIG.replace('files: ["receipt.txt"]', 'files: ["receipt.txt", "other.txt"]'))
    proc = run_rf(["check"], project)
    assert "configuration changed" in proc.stdout


def test_report_and_explain_commands(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    write(project / "deploy.py", DEPLOY_FAIL)
    run_rf(["check"], project)

    proc = run_rf(["report", "--format", "markdown"], project)
    assert proc.returncode == 0
    assert "# Regression Firewall Report" in proc.stdout

    proc = run_rf(["report", "--format", "json"], project)
    assert proc.returncode == 0
    assert '"verdict": "BLOCK"' in proc.stdout

    report = read_report(project)
    change_id = report["changes"][0]["change_id"]
    proc = run_rf(["explain", change_id], project)
    assert proc.returncode == 0
    assert change_id in proc.stdout

    proc = run_rf(["explain", "zzzz"], project)
    assert proc.returncode == 70


def test_intent_file_drives_expected_classification(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    write(project / "deploy.py", DEPLOY_FAIL)
    intent = {
        "schema_version": 1,
        "task": "Deploy now reports failure and exits non-zero.",
        "expected_changes": [
            {"surface": "cli", "target": "deploy", "category": "exit_code_changed",
             "before": 0, "after": 1, "note": "requested failure signal"},
            {"surface": "cli", "target": "deploy", "category": "stdout_changed",
             "note": "message updated to match"},
        ],
    }
    write(project / ".regression-firewall" / "intent.json", json.dumps(intent, indent=2))
    proc = run_rf(["check"], project)
    assert proc.returncode == 0, proc.stdout  # everything expected -> PASS
    report = read_report(project)
    assert report["verdict"] == "PASS"
    assert all(c["classification"] == "expected" for c in report["changes"])
    assert report["intent"]["task"].startswith("Deploy now reports")


def test_discover_reports_project(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    proc = run_rf(["discover"], project)
    assert proc.returncode == 0
    assert "deploy.py" in proc.stdout or "deploy" in proc.stdout
    assert "python" in proc.stdout
