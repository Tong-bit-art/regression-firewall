from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .capture.base import run_capture
from .config.loader import config_hash, find_config_file, load_config
from .config.schema import ConfigError
from .diff import diff_surfaces
from .intent.matcher import classify_change
from .intent.model import IntentError, load_intent
from .models.result import CheckResult
from .models.snapshot import Snapshot
from .normalize.engine import Normalizer
from .report.console import render_console
from .report.json_report import report_to_dict
from .report.markdown import render_markdown
from .scoring.risk import score_changes

EXIT_OK = 0
EXIT_REVIEW = 1
EXIT_BLOCK = 3
EXIT_ERROR = 70

ARTIFACTS_DIR = ".regression-firewall"
INTENT_FILENAME = "intent.json"

VERDICT_EXIT = {"PASS": EXIT_OK, "REVIEW": EXIT_REVIEW, "BLOCK": EXIT_BLOCK}

INIT_TEMPLATE = """\
# Regression Firewall configuration
# See docs/NORMALIZATION.md (normalization rules) and docs/RISK_MODEL.md
# (thresholds and verdicts) in the project repository.

version: 1

surfaces:
  http:
    enabled: true
    # Point at a running server, or let the tool manage one for you:
    #   server:
    #     command: ["python", "server.py"]
    # If base_url contains {port}, the tool picks a free port and passes it
    # to the server via the REGFW_SERVER_PORT environment variable.
    base_url: "http://127.0.0.1:8000"
    probes: []
      # - id: "POST /login"
      #   method: POST
      #   path: /login
      #   body: {"username": "alice", "password": "wrong"}

  cli:
    enabled: true
    probes: []
      # - id: deploy
      #   command: ["python", "deploy.py"]
      #   files: ["out/receipt.json"]   # generated files to watch

  public_api:
    enabled: true
    probes: []
      # - id: mypackage
      #   module: mypackage

ignore:
  headers: [date, content-length]
  json_paths: []

normalization:
  uuid: true
  iso_datetime: true
  epoch_timestamps: true
  request_ids: true
  tokens: true
  temp_paths: true
  durations: true
  float_precision: true
  whitespace: true
  ansi: true

thresholds:
  review_score: 30
  block_score: 70
  block_on_high: true

report:
  markdown: true
  json: true
"""


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        prog="regression-firewall",
        description=(
            "A behavioral regression safety layer for AI coding agents. "
            "Capture behavior before an AI code change, compare afterwards, "
            "and block on unintended regressions."
        ),
    )
    parser.add_argument("--project", default=".", help="project root (default: current directory)")
    parser.add_argument("--version", action="version", version=f"regression-firewall {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="detect the project and scaffold configuration")\
        .add_argument("--force", action="store_true", help="overwrite an existing config file")

    subparsers.add_parser("discover", help="report detected project type and behavior surfaces")

    baseline = subparsers.add_parser("baseline", help="capture current behavior as the baseline")
    baseline.add_argument("--config", default=None, help="path to the config file")
    baseline.add_argument(
        "--force",
        action="store_true",
        help="overwrite the baseline even when the previous check reported "
             "BLOCK/REVIEW (explicit acknowledgment that the old baseline is retired)",
    )

    check = subparsers.add_parser("check", help="re-capture behavior and compare against the baseline")
    check.add_argument("--config", default=None, help="path to the config file")
    check.add_argument("--intent", default=None,
                       help="path to intent.json (default: .regression-firewall/intent.json)")

    report_cmd = subparsers.add_parser("report", help="re-display the latest report")
    report_cmd.add_argument("--format", choices=("console", "markdown", "json"), default="console")

    explain = subparsers.add_parser("explain", help="print full detail for one change id")
    explain.add_argument("change_id", help="change id (or unambiguous prefix) from the report")

    args = parser.parse_args(argv)
    root = Path(args.project).resolve()

    handlers = {
        "init": cmd_init,
        "discover": cmd_discover,
        "baseline": cmd_baseline,
        "check": cmd_check,
        "report": cmd_report,
        "explain": cmd_explain,
    }
    try:
        return handlers[args.command](args, root)
    except (ConfigError, IntentError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


# ---------------------------------------------------------------------------
# Commands


def cmd_init(args, root: Path) -> int:
    config_path = find_config_file(root)
    if config_path is not None and not args.force:
        print(f"error: config already exists at {config_path.name} (use --force to overwrite)",
              file=sys.stderr)
        return EXIT_ERROR

    from .discovery.project import detect_project

    project = detect_project(root)
    target = root / ".regression-firewall.yml"
    target.write_text(INIT_TEMPLATE, encoding="utf-8", newline="\n")
    (root / ARTIFACTS_DIR).mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(root)

    print("Regression Firewall")
    print(f"  Created: {target.name}")
    print(f"  Created: {ARTIFACTS_DIR}/")
    print(f"  Detected project: {project.name} ({project.summary()})")
    if project.package_name:
        print(f"  Suggested public_api probe module: {project.package_name}")
    print()
    print("Next steps:")
    print("  1. Add probes under surfaces: (see the commented examples in the config)")
    print("  2. regression-firewall discover   # verify what will be captured")
    print("  3. regression-firewall baseline   # capture behavior before changes")
    return EXIT_OK


def cmd_discover(args, root: Path) -> int:
    cfg, warnings, _ = load_config(root, args_config(args))
    for warning in warnings:
        print(f"note: {warning}")

    from .discovery.project import detect_project
    from .discovery.routes import discover_routes

    project = detect_project(root)
    print("Regression Firewall — Discovery")
    print(f"  Project:   {project.name}")
    print(f"  Language:  {project.language}")
    print(f"  Framework: {', '.join(project.frameworks) if project.frameworks else '(none detected)'}")
    if project.package_name:
        print(f"  Package:   {project.package_name}")

    print()
    if cfg.http.enabled:
        if cfg.http.discover_app:
            routes, error = discover_routes(cfg.http.discover_app, root)
            if error:
                print(f"  HTTP: route discovery failed: {error}")
            else:
                print(f"  HTTP: {len(routes)} route(s) discovered from {cfg.http.discover_app}")
                for route in routes[:50]:
                    methods = ",".join(route["methods"])
                    print(f"    {methods:<8} {route['path']}")
                if len(routes) > 50:
                    print(f"    ... and {len(routes) - 50} more")
        else:
            print("  HTTP: set surfaces.http.discover_app (e.g. 'app.main:app') to list routes;")
            print("        probes define what is actually captured.")
    if cfg.cli.enabled:
        print(f"  CLI: {len(cfg.cli.probes)} probe(s) configured")
        for probe in cfg.cli.probes:
            print(f"    {' '.join(probe.command)}")
    if cfg.public_api.enabled:
        print(f"  Public API: {len(cfg.public_api.probes)} probe(s) configured")
        for probe in cfg.public_api.probes:
            print(f"    module {probe.module}")
    return EXIT_OK


def cmd_baseline(args, root: Path) -> int:
    cfg, warnings, _ = load_config(root, args_config(args))
    artifacts = root / ARTIFACTS_DIR
    artifacts.mkdir(parents=True, exist_ok=True)

    rebaseline_info = _rebaseline_decision(artifacts, force=getattr(args, "force", False))
    if rebaseline_info.get("refused"):
        return EXIT_ERROR

    snapshot, capture_warnings = run_capture(cfg, root, artifacts)
    snapshot.provenance["snapshot_hash"] = snapshot.content_hash()
    if rebaseline_info:
        snapshot.provenance["rebaseline"] = rebaseline_info
    _write_json(artifacts / "baseline.json", snapshot.to_dict())

    warnings = warnings + capture_warnings
    print("Regression Firewall — Baseline")
    print(f"  Project: {snapshot.project.get('name', '?')} ({snapshot.project.get('language', '?')})")
    print(f"  Probes captured: {snapshot.probe_count()}")
    for surface in ("http", "cli", "public_api"):
        captures = snapshot.captures(surface)
        if captures:
            failed = sum(1 for c in captures if not c.ok)
            status = f"{len(captures)} captured" + (f", {failed} failed" if failed else "")
            print(f"    {surface}: {status}")
    if snapshot.probe_count() == 0:
        print("  WARNING: no probes are configured; nothing was captured.")
        print("           Add probes to .regression-firewall.yml and re-run.")
    for warning in warnings:
        print(f"  WARNING: {warning}")
    git = snapshot.provenance.get("git") or {}
    if git.get("git_available"):
        print(f"  Provenance: commit {str(git.get('git_commit'))[:12]}, "
              f"working tree {'dirty' if git.get('git_dirty') else 'clean'}")
    else:
        print("  Provenance: git not available (commit/dirty not recorded)")
    if rebaseline_info.get("previous_verdict") in ("BLOCK", "REVIEW"):
        print("  BASELINE TRUST WARNING: this baseline replaces one whose last check "
              f"reported {rebaseline_info['previous_verdict']}.")
        print("  Future checks will carry the same warning until a fresh, "
              "pre-change baseline is justified by the user.")
    print(f"  Saved: {ARTIFACTS_DIR}/baseline.json")
    print()
    print("Baseline captured. Now make the code change, then run:")
    print("  regression-firewall check")
    return EXIT_OK


def _rebaseline_decision(artifacts: Path, force: bool) -> dict:
    """Inspect the baseline/report being replaced. A previous non-PASS check
    followed by a new baseline is the classic 'silence the regression' move:
    refuse it without --force, and record it either way so later checks can
    warn. Never deletes the old baseline (it is archived as
    baseline.previous.json on forced replacement)."""
    baseline_path = artifacts / "baseline.json"
    if not baseline_path.is_file():
        return {}

    previous = _read_snapshot_if_valid(baseline_path)
    previous_verdict = None
    report_path = artifacts / "report.json"
    if report_path.is_file():
        try:
            previous_verdict = _read_json(report_path).get("verdict")
        except (OSError, json.JSONDecodeError):
            previous_verdict = None

    info = {}
    if previous is not None:
        info = {
            "previous_captured_at": previous.created_at,
            "previous_snapshot_hash": (previous.provenance or {}).get("snapshot_hash"),
        }
    if previous_verdict in ("BLOCK", "REVIEW"):
        info["previous_verdict"] = previous_verdict
        print("BASELINE TRUST WARNING")
        print(f"The previous check reported {previous_verdict}. Capturing a new baseline now")
        print("would erase the comparison point and let an unintended change pass as")
        print("baseline behavior.")
        if not force:
            print()
            print("Refusing to overwrite. If this is genuinely intentional (e.g. the user")
            print("changed direction), run:  regression-firewall baseline --force")
            print("The previous baseline is archived, and later checks will warn about it.")
            return {"refused": True, **info}
        info["forced"] = True
        previous_file = artifacts / "baseline.previous.json"
        try:
            (artifacts / "baseline.json").replace(previous_file)
        except OSError as exc:
            print(f"warning: could not archive the previous baseline: {exc}")
        print("Proceeding with --force; the previous baseline was archived to "
              "baseline.previous.json.")
        print()
    return info


def _read_snapshot_if_valid(path: Path):
    try:
        return _read_snapshot(path)
    except (ConfigError, OSError, json.JSONDecodeError):
        return None


def cmd_check(args, root: Path) -> int:
    cfg, warnings, _ = load_config(root, args_config(args))
    artifacts = root / ARTIFACTS_DIR
    baseline_path = artifacts / "baseline.json"
    if not baseline_path.is_file():
        print(
            f"error: no baseline found at {baseline_path}. "
            "Run 'regression-firewall baseline' before modifying code.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    baseline = _read_snapshot(baseline_path)

    trust_warning = False
    baseline_warnings = []
    provenance = baseline.provenance or {}
    stored_hash = provenance.get("snapshot_hash")
    if stored_hash:
        actual_hash = baseline.content_hash()
        if stored_hash != actual_hash:
            baseline_warnings.append(
                "the baseline file's contents do not match its recorded snapshot_hash; "
                "it may have been edited by hand"
            )
    rebaseline = provenance.get("rebaseline") or {}
    if rebaseline.get("previous_verdict") in ("BLOCK", "REVIEW"):
        trust_warning = True
        baseline_warnings.append(
            "BASELINE TRUST WARNING: the baseline was replaced with --force after a "
            f"check that reported {rebaseline['previous_verdict']}. It may no longer "
            "represent pre-change behavior; treat this result with reduced trust and "
            "confirm with the user."
        )
    warnings = warnings + baseline_warnings

    latest, capture_warnings = run_capture(cfg, root, artifacts)
    _write_json(artifacts / "latest.json", latest.to_dict())

    normalizer = Normalizer(cfg.normalization, cfg.ignore)
    changes, diff_warnings = diff_surfaces(baseline, latest, normalizer, cfg)
    warnings = warnings + capture_warnings + diff_warnings

    config_changed = bool(baseline.config_hash) and baseline.config_hash != config_hash(cfg)

    intent_path = Path(args.intent) if args.intent else artifacts / INTENT_FILENAME
    if args.intent and not intent_path.is_file():
        print(f"error: intent file not found: {intent_path}", file=sys.stderr)
        return EXIT_ERROR
    intent = load_intent(intent_path)
    warnings.extend(_wildcard_intent_warnings(intent))
    for change in changes:
        change.classification, change.note = classify_change(change, intent)

    score, verdict, floored, _contributions = score_changes(changes, cfg.thresholds)

    result = CheckResult(
        verdict=verdict,
        score=score,
        score_floored=floored,
        changes=changes,
        intent_source=intent.source,
        intent_task=intent.task or None,
        config_changed_since_baseline=config_changed,
        baseline_trust_warning=trust_warning,
        warnings=warnings,
        created_at=latest.created_at,
        tool_version=__version__,
        project=latest.project,
    )

    _write_json(artifacts / "report.json", report_to_dict(result))
    if cfg.report.markdown:
        report_md = artifacts / "report.md"
        report_md.write_text(render_markdown(result) + "\n", encoding="utf-8", newline="\n")

    print(render_console(result))
    return VERDICT_EXIT[verdict]


def cmd_report(args, root: Path) -> int:
    report_path = root / ARTIFACTS_DIR / "report.json"
    if not report_path.is_file():
        print("error: no report found. Run 'regression-firewall check' first.", file=sys.stderr)
        return EXIT_ERROR
    result = CheckResult.from_dict(_read_json(report_path))
    if args.format == "json":
        print(json.dumps(report_to_dict(result), indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(render_markdown(result))
    else:
        print(render_console(result))
    return EXIT_OK


def cmd_explain(args, root: Path) -> int:
    report_path = root / ARTIFACTS_DIR / "report.json"
    if not report_path.is_file():
        print("error: no report found. Run 'regression-firewall check' first.", file=sys.stderr)
        return EXIT_ERROR
    result = CheckResult.from_dict(_read_json(report_path))
    matches = [c for c in result.changes if c.change_id.startswith(args.change_id)]
    if len(matches) == 0:
        print(f"error: no change matches id prefix {args.change_id!r}", file=sys.stderr)
        return EXIT_ERROR
    if len(matches) > 1:
        ids = ", ".join(c.change_id for c in matches)
        print(f"error: id prefix {args.change_id!r} is ambiguous ({ids})", file=sys.stderr)
        return EXIT_ERROR
    change = matches[0]
    print(f"Change {change.change_id}")
    print(f"  Surface:   {change.surface}")
    print(f"  Target:    {change.target}")
    print(f"  Category:  {change.category}")
    if change.path:
        print(f"  Path:      {change.path}")
    print(f"  Class:     {change.classification}" + (f" ({change.note})" if change.note else ""))
    print(f"  Severity:  {change.severity}")
    print(f"  Confidence: {int(round(change.confidence * 100))}%")
    print(f"  Before:    {_fmt_value(change.before)}")
    print(f"  After:     {_fmt_value(change.after)}")
    if change.evidence:
        print(f"  Evidence:  {json.dumps(change.evidence, ensure_ascii=False, default=str)}")
    print(f"  Description: {change.describe()}")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Helpers


def _wildcard_intent_warnings(intent) -> list:
    """An intent entry with every field wildcarded blesses any change as
    EXPECTED; surface it loudly instead of silently trusting the file."""
    warnings = []
    for index, expected in enumerate(intent.expected_changes):
        if expected.surface == "*" and expected.target == "*" and expected.category == "*":
            warnings.append(
                f"intent entry #{index} matches every change (all fields wildcarded); "
                "it marks all changes EXPECTED — narrow it to what the user actually asked for"
            )
    return warnings


def args_config(args):
    return getattr(args, "config", None)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_snapshot(path: Path) -> Snapshot:
    try:
        return Snapshot.from_dict(_read_json(path))
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _ensure_gitignore(root: Path) -> None:
    entry = ".regression-firewall/"
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        content = gitignore.read_text(encoding="utf-8", errors="replace")
        if entry in content.splitlines():
            return
        if not content.endswith("\n"):
            content += "\n"
        content += f"\n# Regression Firewall artifacts (baselines are machine-local)\n{entry}\n"
        gitignore.write_text(content, encoding="utf-8", newline="\n")
    else:
        gitignore.write_text(f"# Regression Firewall artifacts (baselines are machine-local)\n{entry}\n",
                             encoding="utf-8", newline="\n")


def _fmt_value(value) -> str:
    if isinstance(value, str):
        text = value.replace("\n", "\\n")
        return text if len(text) <= 200 else text[:197] + "..."
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
