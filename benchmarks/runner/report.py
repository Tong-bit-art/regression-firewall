"""Benchmark evaluation, metrics, and result writers. Numbers are computed,
never hand-written."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
DOC_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "BENCHMARK_RESULTS.md"

CASE_CLASSES = ("BENCHMARK_PASS", "REGRESSION_FIREWALL_FAILURE",
                "REPOSITORY_SETUP_FAILURE", "INFRASTRUCTURE_FAILURE",
                "MUTATION_FAILURE", "TIMEOUT")

# Case types that plant a real regression (recall denominator). Everything
# else — controls, noise, implementation-only — measures false positives.
NOISE_TYPES = {"no_change_control", "non_behavior_change_control",
               "timestamp_noise", "request_id_noise", "temp_file_noise",
               "implementation_only"}


@dataclass
class ExpectedEntry:
    surface: str
    category: str = "*"
    classification: str = "unexpected"
    severity: str = "*"
    target: str = "*"

    def matches(self, change: dict) -> bool:
        if change.get("surface") != self.surface:
            return False
        if self.target not in ("*", change.get("target")):
            return False
        if self.category not in ("*", change.get("category")):
            return False
        if self.classification not in ("*", change.get("classification")):
            return False
        if self.severity not in ("*", change.get("severity")):
            return False
        return True


@dataclass
class CaseResult:
    repo_id: str
    case_id: str
    case_type: str
    case_class: str  # one of CASE_CLASSES
    expected_verdict: str = ""
    detected_verdict: str = ""
    verdict_ok: bool = False
    missing: list = field(default_factory=list)
    extras: list = field(default_factory=list)  # human-readable strings
    false_positive_count: int = 0
    severity_checked: bool = False
    severity_ok: bool = False
    note: str = ""
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.case_class == "BENCHMARK_PASS"


def evaluate_case(case: dict, report: dict) -> CaseResult:
    """Compare a check report against the case's ground truth.

    Every expected entry must be found among detected changes. Extras are
    triaged: an extra is a false_positive unless ground truth lists it under
    expected_extras (a direct mechanical consequence of the mutation).
    """
    ground = case.get("expected", {})
    expected = [ExpectedEntry(**e) for e in ground.get("changes", [])]
    allowed = [ExpectedEntry(**e) for e in ground.get("expected_extras", [])]
    changes = report.get("changes", [])

    unmatched = list(expected)
    matched_ids = set()
    severity_ok = True
    for change in changes:
        for entry in unmatched:
            if entry.matches(change):
                unmatched.remove(entry)
                matched_ids.add(change["change_id"])
                if entry.severity not in ("*", "") and entry.severity != change.get("severity"):
                    severity_ok = False
                break

    extras = [c for c in changes if c["change_id"] not in matched_ids]
    false_positives = [c for c in extras if not any(a.matches(c) for a in allowed)]

    expected_verdict = ground.get("verdict", "")
    detected_verdict = report.get("verdict", "")

    missing = [f"{e.surface}/{e.category}/{e.classification}/{e.severity}"
               for e in unmatched]
    case_class = "BENCHMARK_PASS"
    if missing or false_positives or expected_verdict != detected_verdict:
        case_class = "REGRESSION_FIREWALL_FAILURE"

    return CaseResult(
        repo_id=case["repo_id"], case_id=case["id"], case_type=case["type"],
        case_class=case_class,
        expected_verdict=expected_verdict, detected_verdict=detected_verdict,
        verdict_ok=expected_verdict == detected_verdict,
        missing=missing,
        extras=[f"{c['surface']}/{c['target']}/{c['category']}"
                f" ({c['classification']}/{c['severity']})" for c in extras],
        false_positive_count=len(false_positives),
        severity_checked=bool(expected) and all(e.severity not in ("*", "") for e in expected),
        severity_ok=severity_ok,
    )


def compute_metrics(results: list) -> dict:
    ran = [r for r in results
           if r.case_class in ("BENCHMARK_PASS", "REGRESSION_FIREWALL_FAILURE")]
    planted = [r for r in ran if r.case_type not in NOISE_TYPES]
    noise = [r for r in ran if r.case_type in NOISE_TYPES]

    tp = sum(1 for r in planted if not r.missing)
    fn = len(planted) - tp
    fp = sum(r.false_positive_count for r in results) + sum(
        1 for r in noise if r.case_class == "REGRESSION_FIREWALL_FAILURE")
    noise_clean = sum(1 for r in noise if r.case_class == "BENCHMARK_PASS")

    severity_checked = [r for r in planted if r.severity_checked]
    return {
        "cases_total": len(results),
        "cases_ran_to_verdict": len(ran),
        "repository_setup_failures": sum(1 for r in results if r.case_class == "REPOSITORY_SETUP_FAILURE"),
        "infrastructure_failures": sum(1 for r in results if r.case_class == "INFRASTRUCTURE_FAILURE"),
        "mutation_failures": sum(1 for r in results if r.case_class == "MUTATION_FAILURE"),
        "timeouts": sum(1 for r in results if r.case_class == "TIMEOUT"),
        "planted_regression_cases": len(planted),
        "detected_regressions": tp,
        "missed_regressions": fn,
        "false_positives": fp,
        "noise_or_control_cases": len(noise),
        "noise_or_control_clean": noise_clean,
        "detection_recall": round(tp / len(planted), 4) if planted else None,
        "false_positive_rate": round(fp / (fp + tp), 4) if (fp + tp) else None,
        "severity_accuracy": (round(sum(1 for r in severity_checked if r.severity_ok)
                                    / len(severity_checked), 4)
                              if severity_checked else None),
        "verdict_accuracy": (round(sum(1 for r in ran if r.verdict_ok) / len(ran), 4)
                             if ran else None),
    }


def write_results(summary: dict, results: list, meta: dict) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "history").mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": 1,
        "generated_at": now.isoformat(timespec="seconds"),
        "isolation": meta.get("isolation"),
        "tool_version": meta.get("tool_version"),
        "python_version": meta.get("python_version"),
        "os": meta.get("os"),
        "manifest_hash": meta.get("manifest_hash"),
        "metrics": summary,
        "cases": [asdict(r) for r in results],
        "notes": meta.get("notes", []),
    }
    out = RESULTS_DIR / "latest.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    shutil.copyfile(out, RESULTS_DIR / "history" /
                    f"{now.strftime('%Y%m%dT%H%M%SZ')}.json")
    return out


def write_markdown_doc(summary: dict, results: list, meta: dict) -> Path:
    lines = ["# Real-World Benchmark Results",
             "",
             f"*Generated {meta.get('generated_at')} by regression-firewall "
             f"{meta.get('tool_version')}. Numbers are computed from "
             "benchmarks/results/latest.json — see docs/BENCHMARK_DESIGN.md for "
             "methodology.*",
             "",
             f"- Isolation: `{meta.get('isolation')}` "
             "(**SECURITY LIMITATION**: no container isolation available on this "
             "machine — scrubbed-environment local execution only)",
             f"- Repositories: {len(meta.get('repos', []))} (pinned commits)",
             f"- Manifest hash: `{str(meta.get('manifest_hash', ''))[:12]}`",
             "",
             "## Metrics",
             "",
             "| Metric | Value |", "|---|---|"]
    for key, value in summary.items():
        lines.append(f"| {key} | {value} |")
    lines += ["", "## Case detail", "",
              "| Repo | Case | Type | Class | Verdict (expected → detected) |",
              "|---|---|---|---|---|"]
    for r in results:
        lines.append(
            f"| {r.repo_id} | {r.case_id} | {r.case_type} | {r.case_class} "
            f"| {r.expected_verdict or '—'} → {r.detected_verdict or '—'} |")
    lines += ["", "## Findings (REGRESSION_FIREWALL_FAILURE cases)", ""]
    failures = [r for r in results if r.case_class == "REGRESSION_FIREWALL_FAILURE"]
    if not failures:
        lines.append("None in this run.")
    else:
        for r in failures:
            lines.append(f"- **{r.repo_id}/{r.case_id}** ({r.case_type}): "
                         f"missing={r.missing or 'none'}; "
                         f"extras={r.extras or 'none'}")
    lines.append("")
    lines.extend(meta.get("notes", []))
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return DOC_PATH
