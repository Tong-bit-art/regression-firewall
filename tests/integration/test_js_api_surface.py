"""End-to-end js_api surface: baseline -> mutate -> check through the CLI."""

import json

from regression_firewall import cli

ENTRY = """\\
export function createApp(name: string, options = {}): App {
  return { name };
}

export class App {
  start(): void {}
}

export const version = "1.0";

export default function bootstrap() {}
"""

INDEX = """\\
export { createApp, App } from './entry';
export * from './consts';
"""


def _project(tmp_path):
    (tmp_path / "src" / "entry.ts").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "entry.ts").write_text(ENTRY, encoding="utf-8")
    (tmp_path / "src" / "index.ts").write_text(INDEX, encoding="utf-8")
    (tmp_path / ".regression-firewall.yml").write_text(
        "version: 1\n"
        "surfaces:\n"
        "  http: {enabled: false}\n"
        "  cli: {enabled: false}\n"
        "  public_api: {enabled: false}\n"
        "  js_api:\n"
        "    probes:\n"
        "      - id: pkg\n"
        "        file: src/index.ts\n",
        encoding="utf-8",
    )


def test_capture_includes_resolved_reexports(tmp_path):
    _project(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    snapshot = json.loads(
        (tmp_path / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    symbols = snapshot["surfaces"]["js_api"][0]["data"]["symbols"]
    # createApp/App via named re-export, version via export * from consts
    assert "createApp" in symbols
    assert "App" in symbols
    assert symbols["createApp"]["signature"] == "(name, options?)"


def test_symbol_removed_blocks(tmp_path):
    _project(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    entry = tmp_path / "src" / "entry.ts"
    entry.write_text(
        ENTRY.replace("export function createApp(name: string, options = {}): App {",
                      "function createApp(name: string, options = {}): App {"),
        encoding="utf-8",
    )
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_BLOCK
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    by_id = {(c["target"], c["category"]): c for c in report["changes"]}
    removed = by_id[("src/index.ts:createApp", "symbol_removed")]
    assert removed["classification"] == "unexpected"
    assert removed["severity"] == "critical"


def test_signature_change_reviews(tmp_path):
    _project(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    entry = tmp_path / "src" / "entry.ts"
    entry.write_text(
        ENTRY.replace("export function createApp(name: string, options = {}): App {",
                      "export function createApp(name: string, options = {}, mode = 'x'): App {"),
        encoding="utf-8",
    )
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_REVIEW
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    change = next(c for c in report["changes"]
                  if c["target"] == "src/index.ts:createApp"
                  and c["category"] == "signature_changed")
    assert change["before"] == "(name, options?)"
    assert change["after"] == "(name, options?, mode?)"


def test_no_change_control_passes(tmp_path):
    _project(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    # comment-only edit must not change the public surface
    entry = tmp_path / "src" / "entry.ts"
    entry.write_text("// touched\n" + ENTRY, encoding="utf-8")
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_OK


def test_intent_makes_addition_expected(tmp_path):
    _project(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    entry = tmp_path / "src" / "entry.ts"
    entry.write_text(ENTRY + "\nexport function shutdown(): void {}\n", encoding="utf-8")
    artifacts = tmp_path / ".regression-firewall"
    (artifacts / "intent.json").write_text(json.dumps({
        "schema_version": 1,
        "task": "add shutdown()",
        "expected_changes": [
            {"surface": "js_api", "target": "src/index.ts:shutdown",
             "category": "symbol_added", "note": "requested"}
        ],
    }, indent=2) + "\n", encoding="utf-8")
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_OK


def test_missing_entry_file_blocks(tmp_path):
    _project(tmp_path)
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    (tmp_path / "src" / "index.ts").unlink()
    # the entry file vanishing is itself a high-severity regression signal
    exit_code = cli.main(["--project", str(tmp_path), "check"])
    assert exit_code == cli.EXIT_BLOCK
    report = json.loads(
        (tmp_path / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )
    assert any(c["category"] == "capture_error" for c in report["changes"])
