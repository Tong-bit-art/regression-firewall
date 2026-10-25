"""Benchmark evaluator guards. The holdout run of 2026-10-25 crashed here
when an expected entry used a `path` field the evaluator did not know."""

from benchmarks.runner.report import ExpectedEntry, evaluate_case


def test_expected_entry_path_matching():
    entry = ExpectedEntry(surface="cli", category="file_created",
                          classification="uncertain", path="out/x.txt")
    assert entry.matches({"surface": "cli", "category": "file_created",
                          "path": "out/x.txt", "classification": "uncertain"})
    assert not entry.matches({"surface": "cli", "category": "file_created",
                              "path": "out/y.txt", "classification": "uncertain"})
    # a change without a path cannot satisfy a path-specific entry
    assert not entry.matches({"surface": "cli", "category": "file_created",
                              "path": None, "classification": "uncertain"})


def test_expected_entry_path_wildcard_default():
    entry = ExpectedEntry(surface="cli", category="file_created",
                          classification="uncertain")
    assert entry.matches({"surface": "cli", "category": "file_created",
                          "path": "any", "classification": "uncertain"})


def test_evaluate_case_with_path_entries():
    case = {
        "repo_id": "r",
        "id": "c",
        "type": "generated_file_added",
        "expected": {
            "changes": [
                {"surface": "cli", "target": "fmt", "category": "file_created",
                 "path": "bench_sample/x.txt", "classification": "uncertain",
                 "severity": "medium"},
            ],
            "verdict": "REVIEW",
        },
    }
    report = {
        "verdict": "REVIEW",
        "changes": [
            {"surface": "cli", "target": "fmt", "category": "file_created",
             "path": "bench_sample/x.txt", "classification": "uncertain",
             "severity": "medium", "change_id": "a1"},
        ],
    }
    result = evaluate_case(case, report)
    assert result.case_class == "BENCHMARK_PASS"
    assert result.false_positive_count == 0


def test_evaluate_case_skipped_probes_min():
    case = {
        "repo_id": "r", "id": "c", "type": "no_change_control",
        "expected": {"changes": [], "verdict": "REVIEW", "skipped_probes_min": 2},
    }
    ok_report = {"verdict": "REVIEW", "changes": [],
                 "selection": {"cli": {"a": "r1", "b": "r2"}}}
    assert evaluate_case(case, ok_report).case_class == "BENCHMARK_PASS"
    thin_report = {"verdict": "REVIEW", "changes": [],
                   "selection": {"cli": {"a": "r1"}}}
    result = evaluate_case(case, thin_report)
    assert result.case_class == "REGRESSION_FIREWALL_FAILURE"
    assert any("skipped_probes=1" in m for m in result.missing)
