"""Deterministic eval runner.

Plants known regressions into tiny real projects, runs the full
``baseline -> mutate -> check`` pipeline through the real CLI in a
subprocess, and scores detection. See docs/EVALS.md.

Usage:
    python -m evals.runner [--filter PREFIX] [--keep]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = Path(__file__).resolve().parent / "cases"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


@dataclasses.dataclass
class CaseResult:
    case_id: str
    name: str
    surface: str
    ok: bool = False
    verdict_ok: bool = False
    changes_ok: bool = False
    expected_verdict: str = ""
    detected_verdict: str = ""
    missing: list = dataclasses.field(default_factory=list)
    extras: list = dataclasses.field(default_factory=list)
    expected_entries: list = dataclasses.field(default_factory=list)
    error: str = ""
    duration_s: float = 0.0


def run_cli(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "regression_firewall"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_case(case_dir: Path, work_root: Path) -> CaseResult:
    spec = yaml.safe_load((case_dir / "case.yml").read_text(encoding="utf-8"))
    result = CaseResult(
        case_id=case_dir.name.split("_", 1)[0],
        name=spec.get("name", case_dir.name),
        surface=spec.get("surface", "?"),
        expected_entries=spec.get("expect", {}).get("changes") or [],
    )
    started = time.monotonic()
    project = work_root / case_dir.name
    try:
        shutil.copytree(case_dir / "before", project)

        baseline = run_cli(["baseline"], project)
        if baseline.returncode != 0:
            result.error = f"baseline failed: {baseline.stderr[-400:] or baseline.stdout[-400:]}"
            return result

        for mutation in spec.get("mutations") or []:
            target = project / mutation["file"]
            text = target.read_text(encoding="utf-8")
            find, replace = mutation["find"], mutation["replace"]
            if find not in text:
                result.error = (
                    f"case authoring error: find-text not found in {mutation['file']}: {find!r}"
                )
                return result
            target.write_text(text.replace(find, replace), encoding="utf-8", newline="\n")

        if spec.get("intent"):
            intent_dir = project / ".regression-firewall"
            intent_dir.mkdir(exist_ok=True)
            (intent_dir / "intent.json").write_text(
                json.dumps(spec["intent"], indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )

        check = run_cli(["check"], project)
        report_path = project / ".regression-firewall" / "report.json"
        if not report_path.is_file():
            result.error = f"check produced no report: {check.stderr[-400:]}"
            return result
        report = json.loads(report_path.read_text(encoding="utf-8"))

        result.expected_verdict = spec["expect"]["verdict"]
        result.detected_verdict = report["verdict"]

        detected = list(report["changes"])
        unmatched = list(result.expected_entries)
        matched_ids = set()
        for change in detected:
            for entry in unmatched:
                if _entry_matches(change, entry):
                    unmatched.remove(entry)
                    entry["_detected"] = True
                    matched_ids.add(change["change_id"])
                    break
        result.missing = [
            f"{e.get('surface', '*')}/{e.get('target', '*')}/{e.get('category', '*')}"
            for e in unmatched
        ]
        result.extras = [
            f"{c['surface']}/{c['target']}/{c['category']} "
            f"({c['classification']}/{c['severity']})"
            for c in detected
            if c["change_id"] not in matched_ids
        ]
        result.verdict_ok = result.expected_verdict == result.detected_verdict
        result.changes_ok = not result.missing and not result.extras
        result.ok = result.verdict_ok and result.changes_ok
        return result
    except Exception as exc:  # noqa: BLE001 - runner must report, not crash
        result.error = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        result.duration_s = round(time.monotonic() - started, 2)


def _entry_matches(change: dict, entry: dict) -> bool:
    for key in ("surface", "target", "category"):
        if key in entry and entry[key] != change.get(key):
            return False
    for key in ("classification", "severity"):
        if key in entry and entry[key] != change.get(key):
            return False
    if "path" in entry and entry["path"] != change.get("path"):
        return False
    return True


def aggregate(results: list) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.ok)

    # Detection recall over planted UNEXPECTED entries: an entry counts as
    # planted when its expectation requires classification == "unexpected".
    planted = [
        entry
        for result in results
        for entry in result.expected_entries
        if entry.get("classification") == "unexpected"
    ]
    detected_planted = sum(1 for e in planted if e.get("_detected"))
    recall = (detected_planted / len(planted)) if planted else None

    fp_cases = sum(1 for r in results if r.extras)
    fpr = (fp_cases / total) if total else None

    severity_checked = [e for r in results for e in r.expected_entries if "severity" in e]
    severity_ok = sum(1 for e in severity_checked if e.get("_detected"))
    severity_accuracy = (severity_ok / len(severity_checked)) if severity_checked else None

    intent_entries = [
        e for r in results for e in r.expected_entries if e.get("classification") == "expected"
    ]
    intent_ok = sum(1 for e in intent_entries if e.get("_detected"))
    intent_accuracy = (intent_ok / len(intent_entries)) if intent_entries else None

    verdict_accuracy = (
        sum(1 for r in results if r.verdict_ok) / total if total else None
    )

    return {
        "cases_total": total,
        "cases_passed": passed,
        "detection_recall": recall,
        "false_positive_rate": fpr,
        "false_positive_cases": fp_cases,
        "extra_changes": sum(len(r.extras) for r in results),
        "severity_accuracy": severity_accuracy,
        "expected_change_accuracy": intent_accuracy,
        "verdict_accuracy": verdict_accuracy,
    }


def run_all(work_root: Path | None = None, case_filter: str = "") -> dict:
    case_dirs = sorted(d for d in CASES_DIR.iterdir() if d.is_dir())
    if case_filter:
        case_dirs = [d for d in case_dirs if d.name.startswith(case_filter)]
    if work_root is None:
        work_root = Path(tempfile.mkdtemp(prefix="regfw-evals-"))

    results = []
    for case_dir in case_dirs:
        result = run_case(case_dir, work_root)
        results.append(result)
        status = "PASS" if result.ok else "FAIL"
        detail = ""
        if not result.ok:
            parts = []
            if result.missing:
                parts.append(f"missing={result.missing}")
            if result.extras:
                parts.append(f"extras={result.extras}")
            if not result.verdict_ok:
                parts.append(f"verdict={result.detected_verdict}!={result.expected_verdict}")
            if result.error:
                parts.append(f"error={result.error}")
            detail = "  " + "; ".join(parts)
        print(f"[{status}] {case_dir.name} ({result.duration_s}s){detail}")

    summary = aggregate(results)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(
            {"summary": summary, "cases": [dataclasses.asdict(r) for r in results]},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {"results": results, "summary": summary}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="evals.runner", description=__doc__)
    parser.add_argument("--filter", default="", help="only run cases whose id starts with this prefix")
    parser.add_argument("--keep", action="store_true", help="keep the working directory")
    args = parser.parse_args(argv)

    print("Regression Firewall — Eval Suite")
    work_root = Path(tempfile.mkdtemp(prefix="regfw-evals-"))
    try:
        outcome = run_all(work_root=work_root, case_filter=args.filter)
    finally:
        if not args.keep:
            shutil.rmtree(work_root, ignore_errors=True)

    summary = outcome["summary"]
    print()
    print("Summary")
    for key, value in summary.items():
        if isinstance(value, float):
            value = f"{value:.1%}"
        print(f"  {key}: {value}")
    print(f"  results: evals/results/summary.json")
    return 0 if summary["cases_passed"] == summary["cases_total"] else 1


if __name__ == "__main__":
    sys.exit(main())
