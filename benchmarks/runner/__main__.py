"""Real-world GitHub benchmark runner. See docs/BENCHMARK_DESIGN.md.

Usage:
    python -m benchmarks.runner --split development
    python -m benchmarks.runner --repo flaskr
    python -m benchmarks.runner --list
"""

from __future__ import annotations

import argparse
import hashlib
import os
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

BENCH_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BENCH_DIR.parent
MUTATIONS_DIR = BENCH_DIR / "mutations"

sys.path.insert(0, str(REPO_ROOT))
from benchmarks.runner.executor import get_executor, scrubbed_env  # noqa: E402
from benchmarks.runner.mutations import MutationError, apply_mutation, restore  # noqa: E402
from benchmarks.runner.report import (  # noqa: E402
    compute_metrics, evaluate_case, write_markdown_doc, write_results,
)


def log(msg: str) -> None:
    print(msg, flush=True)


def load_manifest() -> dict:
    manifest_path = BENCH_DIR / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha1(manifest_path.read_bytes()).hexdigest()
    for mfile in sorted(MUTATIONS_DIR.glob("*.yaml")):
        digest = hashlib.sha1(digest.encode() + mfile.read_bytes()).hexdigest()
    return {"manifest": manifest, "hash": digest}


def build_wheel(workspace: Path) -> Path:
    dist = workspace / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    # setuptools' build/ directory accumulates files across builds and does
    # NOT remove sources that were renamed/deleted — a stale build/lib/ would
    # resurrect dead modules into the wheel (observed with a module rename).
    for stale in [REPO_ROOT / "build", *REPO_ROOT.glob("*.egg-info"),
                  REPO_ROOT / "regression_firewall.egg-info"]:
        shutil.rmtree(stale, ignore_errors=True)
    log("[wheel] building regression-firewall wheel from current source")
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(dist)],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"wheel build failed: {proc.stderr[-400:]}")
    wheels = list(dist.glob("regression_firewall-*.whl"))
    if not wheels:
        raise RuntimeError("no wheel produced")
    return wheels[0]


def ensure_repo_clone(repo: dict, workspace: Path, executor) -> Path:
    repos_dir = workspace / "repos"
    repos_dir.mkdir(parents=True, exist_ok=True)
    dest = repos_dir / repo["id"]
    if not dest.exists():
        log(f"[clone] {repo['repo_url']} -> {dest.name}")
        result = None
        for attempt in range(3):
            result = executor.run(["git", "clone", "--quiet", repo["repo_url"], dest.name],
                                  repos_dir, phase="clone")
            if result.ok:
                break
            import shutil as _shutil

            _shutil.rmtree(dest, ignore_errors=True)
            time.sleep(2 * (attempt + 1))
        if not result or not result.ok:
            raise RuntimeError(f"clone failed after retries: {result.stderr[-300:] if result else 'no result'}")
    checkout = executor.run(["git", "checkout", "--quiet", repo["commit_sha"]], dest,
                            phase="command")
    if not checkout.ok:
        fetch = executor.run(["git", "fetch", "--quiet", "origin"], dest, phase="command")
        if not fetch.ok:
            raise RuntimeError(f"fetch failed: {fetch.stderr[-300:]}")
        checkout = executor.run(["git", "checkout", "--quiet", repo["commit_sha"]], dest,
                                phase="command")
        if not checkout.ok:
            raise RuntimeError(f"checkout {repo['commit_sha']} failed: {checkout.stderr[-300:]}")
    return dest


def ensure_venv(repo: dict, workspace: Path, wheel: Path, executor,
                repo_root: Path) -> tuple:
    setup_cwd = repo_root / repo.get("project_root", "") / repo.get("setup_cwd", ".")
    venv_dir = workspace / "venvs" / repo["id"]
    venv_python = venv_dir / "Scripts" / "python.exe"
    if os.name != "nt":
        venv_python = venv_dir / "bin" / "python"
    if not venv_python.exists():
        venv_cmd = [str(part) for part in repo.get("venv_command",
                                                   [sys.executable, "-m", "venv"])]
        log(f"[venv] creating {venv_dir.name} ({venv_cmd[0]})")
        result = executor.run(venv_cmd + [str(venv_dir)], workspace, phase="setup")
        if not result.ok:
            raise RuntimeError(f"venv creation failed: {result.stderr[-300:]}")
    env = scrubbed_env()
    env["VIRTUAL_ENV"] = str(venv_dir)

    steps = [["-m", "pip", "install", "--quiet", "--upgrade", "pip"],
             # uninstall first: same-version wheel reinstalls can leave stale
             # files behind (observed with a renamed module), which silently
             # reintroduces old bugs into the venv
             ["-m", "pip", "uninstall", "--quiet", "-y", "regression-firewall"]]
    for cmd in repo.get("setup_commands", []):
        steps.append([str(part).replace("{venv_python}", str(venv_python)) for part in cmd])
    for step in steps:
        result = executor.run([str(venv_python)] + step, setup_cwd, phase="setup")
        if not result.ok:
            raise RuntimeError(f"setup step failed ({' '.join(step[:3])}...): "
                               f"{result.stderr[-400:] or result.stdout[-400:]}")

    # pip uninstall can leave files behind on Windows (locked/RECORD gaps);
    # remove the package tree outright so the fresh wheel is the only truth.
    import glob

    for sp in glob.glob(str(venv_dir / "Lib" / "site-packages" / "regression_firewall*")) +              glob.glob(str(venv_dir / "lib" / "site-packages" / "regression_firewall*")):
        shutil.rmtree(sp, ignore_errors=True)

    install = executor.run([str(venv_python), "-m", "pip", "install", "--quiet", "--no-cache-dir", str(wheel)],
                           setup_cwd, phase="setup")
    if not install.ok:
        raise RuntimeError(f"wheel install failed: {install.stderr[-400:]}")
    return venv_python, env


def render(value, venv_python: Path, api_key: str = ""):
    if isinstance(value, str):
        return value.replace("{venv_python}", str(venv_python)).replace(
            "{api_key}", api_key)
    if isinstance(value, list):
        return [render(v, venv_python, api_key) for v in value]
    if isinstance(value, dict):
        return {k: render(v, venv_python, api_key) for k, v in value.items()}
    return value


def run_tool(venv_python: Path, args: list, cwd: Path, executor, phase="case",
             extra_env: dict | None = None):
    env = scrubbed_env()
    env.update({k: str(v) for k, v in (extra_env or {}).items()})
    return executor.run_with_env([str(venv_python), "-m", "regression_firewall"] + args,
                                 cwd, phase=phase, env=env)


def read_report(project: Path) -> dict | None:
    report = project / ".regression-firewall" / "report.json"
    if not report.is_file():
        return None
    return json.loads(report.read_text(encoding="utf-8"))


def run_case(venv_python: Path, project: Path, case: dict, executor,
             excludes: list, env: dict) -> tuple:
    started = time.monotonic()
    from benchmarks.runner.report import CaseResult

    def finish(case_class: str, note: str = "", report: dict | None = None) -> CaseResult:
        return CaseResult(
            repo_id=case["repo_id"], case_id=case["id"], case_type=case["type"],
            case_class=case_class, note=note,
            duration_s=round(time.monotonic() - started, 2),
            **(_evaluate_fields(case, report) if report else {}),
        )

    # 1. restore pristine state; each case is an independent scenario, so the
    # previous case's artifacts (incl. its BLOCK report) must not leak in.
    restore(project, project, excludes)
    shutil.rmtree(project / ".regression-firewall", ignore_errors=True)

    # Noise cases apply their mutation BEFORE the baseline so the volatile
    # code is active on both sides and only the values differ.
    pre_baseline = case.get("apply_before_baseline", False)
    if case["type"] not in ("no_change_control",) and pre_baseline:
        try:
            apply_mutation(project, case.get("edits", []))
        except MutationError as exc:
            return finish("MUTATION_FAILURE", str(exc))

    baseline = run_tool(venv_python, ["baseline"], project, executor, extra_env=env)
    if baseline.timeout:
        return finish("TIMEOUT", "baseline timed out")
    if not baseline.ok:
        return finish("REPOSITORY_SETUP_FAILURE",
                      f"baseline exited {baseline.exit_code}: "
                      f"{(baseline.stderr or baseline.stdout)[-300:]}")

    # 2. mutation (unless control; noise cases already applied theirs)
    if case["type"] not in ("no_change_control",) and not pre_baseline:
        try:
            apply_mutation(project, case.get("edits", []))
        except MutationError as exc:
            return finish("MUTATION_FAILURE", str(exc))

    # 3. intent
    if case.get("intent"):
        intent_path = project / ".regression-firewall" / "intent.json"
        intent_path.write_text(json.dumps(case["intent"], indent=2) + "\n",
                               encoding="utf-8", newline="\n")

    # 4. check
    check = run_tool(venv_python, ["check"], project, executor, extra_env=env)
    report = read_report(project)
    if check.timeout:
        return finish("TIMEOUT", "check timed out")
    if report is None:
        return finish("REPOSITORY_SETUP_FAILURE",
                      f"check exited {check.exit_code} without report: "
                      f"{(check.stderr or check.stdout)[-300:]}")

    result = finish("BENCHMARK_PASS", report=report)
    evaluated_class = _evaluate_class(case, report)
    if evaluated_class != "BENCHMARK_PASS":
        result.case_class = evaluated_class
    # 5. cleanup mutation artifacts (intent file)
    intent_path = project / ".regression-firewall" / "intent.json"
    if intent_path.exists():
        intent_path.unlink()
    return result


def _evaluate_class(case: dict, report: dict) -> str:
    from benchmarks.runner.report import evaluate_case

    return evaluate_case(case, report).case_class


def _evaluate_fields(case: dict, report: dict) -> dict:
    from dataclasses import asdict

    evaluated = evaluate_case(case, report)
    data = asdict(evaluated)
    return {k: v for k, v in data.items()
            if k in ("expected_verdict", "detected_verdict", "verdict_ok",
                     "missing", "extras", "false_positive_count",
                     "severity_checked", "severity_ok")}


def run_repo(repo: dict, workspace: Path, wheel: Path, executor) -> list:
    from benchmarks.runner.report import CaseResult

    results: list = []
    repo_id = repo["id"]
    log(f"\n=== repo {repo_id} ({repo['split']}) ===")
    try:
        repo_root = ensure_repo_clone(repo, workspace, executor)
    except RuntimeError as exc:
        log(f"  [INFRASTRUCTURE_FAILURE] {exc}")
        return [CaseResult(repo_id=repo_id, case_id=f"{repo_id}_clone",
                           case_type="clone", case_class="INFRASTRUCTURE_FAILURE",
                           note=str(exc))]
    try:
        venv_python, _env = ensure_venv(repo, workspace, wheel, executor, repo_root)
    except RuntimeError as exc:
        log(f"  [REPOSITORY_SETUP_FAILURE] {exc}")
        return [CaseResult(repo_id=repo_id, case_id=f"{repo_id}_setup",
                           case_type="setup", case_class="REPOSITORY_SETUP_FAILURE",
                           note=str(exc))]

    project = repo_root / repo.get("project_root", "")
    if repo.get("verify_command"):
        verify = [str(c).replace("{venv_python}", str(venv_python))
                  for c in repo["verify_command"]]
        verify_cwd = project / repo.get("setup_cwd", ".")
        result = executor.run(verify, verify_cwd, phase="setup")
        if not result.ok:
            log(f"  [REPOSITORY_SETUP_FAILURE] verify failed: "
                f"{(result.stderr or result.stdout)[-300:]}")
            return [CaseResult(repo_id=repo_id, case_id=f"{repo_id}_verify",
                               case_type="verify", case_class="REPOSITORY_SETUP_FAILURE",
                               note=(result.stderr or result.stdout)[-400:])]

    # write the regression-firewall config with substitutions
    api_key = ""
    if repo.get("api_key_command"):
        cmd = [str(c).replace("{venv_python}", str(venv_python))
               for c in repo["api_key_command"]]
        key_result = executor.run(cmd, project, phase="command")
        api_key = (key_result.stdout or "").strip().splitlines()[-1] if key_result.ok else ""
        if not api_key:
            log(f"  [REPOSITORY_SETUP_FAILURE] could not obtain API key: "
                f"{(key_result.stderr or key_result.stdout)[-300:]}")
            return [CaseResult(repo_id=repo_id, case_id=f"{repo_id}_apikey",
                               case_type="setup", case_class="REPOSITORY_SETUP_FAILURE",
                               note="could not obtain API key")]
    config = render(repo["probes"], venv_python, api_key)
    (project / ".regression-firewall.yml").write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8", newline="\n")

    mutations = yaml.safe_load((MUTATIONS_DIR / f"{repo_id}.yaml").read_text(encoding="utf-8"))
    cases = mutations["cases"]

    excludes = repo.get("clean_excludes", [])
    try:
        results.extend(_run_cases(repo_id, repo, repo_root, project, cases,
                                  venv_python, executor, excludes))
    finally:
        # never leave a mutated tree behind (early returns included)
        restore(project, repo_root, excludes)
    return results


def _run_cases(repo_id: str, repo: dict, repo_root: Path, project: Path,
               cases: list, venv_python: Path, executor, excludes: list) -> list:
    results: list = []
    for case in cases:
        case["repo_id"] = repo_id
        repeats = case.get("repeat", 1)
        for i in range(repeats):
            result = run_case(venv_python, project, case, executor, excludes,
                              repo.get("env", {}))
            if repeats > 1:
                result.case_id = f"{result.case_id}#{i + 1}"
            log(f"  [{result.case_class}] {result.case_id} ({result.duration_s}s)"
                + (f"  {result.note}" if result.note else "")
                + (f"  missing={result.missing}" if result.missing else "")
                + (f"  extras={result.extras}" if result.extras else ""))
            results.append(result)
            if result.case_class in ("REPOSITORY_SETUP_FAILURE", "INFRASTRUCTURE_FAILURE",
                                     "MUTATION_FAILURE"):
                break  # repeating a broken setup is noise
    restore(project, repo_root, excludes)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="benchmarks.runner",
                                     description=__doc__)
    parser.add_argument("--split", choices=("development", "holdout", "all"),
                        default="development")
    parser.add_argument("--repo", default=None, help="run a single repository by id")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)

    loaded = load_manifest()
    manifest = loaded["manifest"]
    repos = manifest["repos"]
    if args.list:
        for repo in repos:
            print(f"{repo['id']:<14} {repo['split']:<12} {repo['commit_sha'][:10]} "
                  f"{repo['repo_url']}")
        return 0

    if args.repo:
        selected = [r for r in repos if r["id"] == args.repo]
        if not selected:
            print(f"unknown repo id: {args.repo}", file=sys.stderr)
            return 2
    else:
        selected = [r for r in repos
                    if args.split == "all" or r["split"] == args.split]

    # Persistent workspace: clones and venvs are reused across runs. Must be
    # an ASCII-only path: flit_core editable installs write raw paths into
    # .pth files, which break under non-ASCII user profiles.
    workspace = Path(os.environ.get("REGFW_BENCH_WORKSPACE",
                                    Path(tempfile.gettempdir()) / "regfw-benchmark"))
    workspace.mkdir(parents=True, exist_ok=True)
    executor = get_executor()
    wheel = build_wheel(workspace)
    log(f"workspace: {workspace}\nwheel: {wheel.name}\n"
        f"isolation: {executor.name} (SECURITY LIMITATION: no container)")

    results = []
    for repo in selected:
        results.extend(run_repo(repo, workspace, wheel, executor))

    meta = {
        "isolation": executor.name,
        "tool_version": _tool_version(),
        "python_version": platform.python_version(),
        "os": platform.platform(),
        "manifest_hash": loaded["hash"],
        "repos": [{"id": r["id"], "url": r["repo_url"], "commit": r["commit_sha"],
                   "license": r["license"], "split": r["split"]} for r in selected],
        "notes": manifest.get("notes", []),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    summary = compute_metrics(results)
    json_path = write_results(summary, results, meta)
    doc_path = write_markdown_doc(summary, results, meta)
    log("\n=== summary ===")
    for key, value in summary.items():
        log(f"  {key}: {value}")
    log(f"results: {json_path}\ndoc: {doc_path}")
    return 0


def _tool_version() -> str:
    from regression_firewall import __version__

    return __version__


if __name__ == "__main__":
    sys.exit(main())
