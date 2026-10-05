import pytest

from evals.runner import run_all


@pytest.fixture(scope="module")
def eval_summary(tmp_path_factory):
    work_root = tmp_path_factory.mktemp("regfw-evals")
    outcome = run_all(work_root=work_root)
    return outcome


def test_all_eval_cases_pass(eval_summary):
    summary = eval_summary["summary"]
    assert summary["cases_total"] == 20, "the eval suite must contain 20 cases"
    failures = [r for r in eval_summary["results"] if not r.ok]
    assert not failures, f"failing cases: {[r.case_id + ' ' + r.error for r in failures]}"


def test_eval_quality_gates(eval_summary):
    """The V0.1 release gate from docs/EVALS.md."""
    summary = eval_summary["summary"]
    assert summary["detection_recall"] >= 0.95
    assert summary["false_positive_rate"] == 0.0
    assert summary["verdict_accuracy"] == 1.0
    assert summary["severity_accuracy"] == 1.0
    assert summary["expected_change_accuracy"] == 1.0
