import pytest

from evals.runner import CASES_DIR, run_all


@pytest.fixture(scope="module")
def eval_summary(tmp_path_factory):
    work_root = tmp_path_factory.mktemp("regfw-evals")
    outcome = run_all(work_root=work_root)
    return outcome


def test_all_eval_cases_pass(eval_summary):
    summary = eval_summary["summary"]
    on_disk = len([d for d in CASES_DIR.iterdir() if d.is_dir()])
    assert summary["cases_total"] == on_disk, (
        "every case directory must run; count the cases, don't pin the number"
    )
    assert summary["cases_total"] >= 21, "the suite must keep growing, never shrink"
    failures = [r for r in eval_summary["results"] if not r.ok]
    assert not failures, f"failing cases: {[r.case_id + ' ' + r.error for r in failures]}"


def test_eval_quality_gates(eval_summary):
    """The V0.1 release gate from docs/EVALS.md."""
    summary = eval_summary["summary"]
    assert summary["detection_recall"] >= 0.95, f"recall={summary['detection_recall']}"
    assert summary["false_positive_rate"] == 0.0,         f"fp={summary['false_positive_rate']} (cases: {[r.case_id for r in eval_summary['results'] if r.extras]})"
    assert summary["verdict_accuracy"] == 1.0,         f"verdicts: {[(r.case_id, r.expected_verdict, r.detected_verdict) for r in eval_summary['results'] if not r.verdict_ok]}"
    assert summary["severity_accuracy"] == 1.0,         f"severity mismatches: {[(r.case_id, r.missing) for r in eval_summary['results'] if not r.severity_ok]}"
    assert summary["expected_change_accuracy"] == 1.0,         f"expected-change misses: {[(r.case_id, r.missing) for r in eval_summary['results'] if not r.ok and r.case_type != 'no_change_control']}"
