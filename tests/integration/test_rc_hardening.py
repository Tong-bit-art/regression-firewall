"""RC hardening tests: baseline provenance, suspicious re-baseline guard,
extended secret redaction, no-change false-positive stability."""

import json
import shutil
import subprocess
import sys

from _fixtures import CLI_CONFIG, DEPLOY_FAIL, DEPLOY_PLAIN, read_report
from conftest import write as _write  # noqa: F401  (write is used via fixture)


# ---------------------------------------------------------------------------
# P1.3 — baseline provenance


def test_baseline_provenance_recorded(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    snap = json.loads(
        (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    prov = snap["provenance"]
    assert snap["tool_version"]
    assert snap["schema_version"] == "1"
    assert snap["created_at"]
    assert snap["config_hash"]
    assert prov["snapshot_hash"]
    # temp dirs are not git repos: graceful degradation, explicitly marked
    assert prov["git"]["git_available"] is False
    assert prov["git"]["git_commit"] is None


def test_baseline_provenance_with_git(project, run_rf, write):
    import shutil

    if shutil.which("git") is None:
        print("git not installed; skipping")
        return
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run(project, ["init", "-q"])
    run(project, ["config", "user.email", "rc@example.com"])
    run(project, ["config", "user.name", "RC"])
    run(project, ["add", "."])
    run(project, ["commit", "-q", "-m", "init"])
    run_rf(["baseline"], project, expect_exit=0)
    snap = json.loads(
        (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    git = snap["provenance"]["git"]
    assert git["git_available"] is True
    assert len(git["git_commit"]) == 40
    assert git["git_dirty"] is False
    # dirty the tree -> next baseline records it
    (project / "extra.txt").write_text("x", encoding="utf-8")
    run_rf(["baseline"], project, expect_exit=0)
    snap = json.loads(
        (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    assert snap["provenance"]["git"]["git_dirty"] is True


def run(cwd, args):
    proc = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_baseline_tamper_detection(project, run_rf, write):
    """Hand-edited baselines must be flagged by check. The project name is
    part of the content hash but not behavior, so the check verdict stays
    PASS while the tamper is surfaced."""
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    snap_path = project / ".regression-firewall" / "baseline.json"
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    snap["project"]["name"] = "tampered-name"
    snap_path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    proc = run_rf(["check"], project)
    assert proc.returncode == 0  # behavior itself unchanged...
    assert "snapshot_hash" in proc.stdout  # ...but the tamper is visible


# ---------------------------------------------------------------------------
# P1.4 — suspicious re-baseline guard


def test_rebaseline_after_block_requires_force_and_warns(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)

    run_rf(["baseline"], project, expect_exit=0)
    write(project / "deploy.py", DEPLOY_FAIL)
    proc = run_rf(["check"], project)
    assert proc.returncode == 3  # BLOCK

    # re-baselining to silence the BLOCK must be refused without --force
    refused = run_rf(["baseline"], project)
    assert refused.returncode == 70
    assert "BASELINE TRUST WARNING" in refused.stdout
    assert "Refusing to overwrite" in refused.stdout
    # the old baseline is untouched
    snap_before = (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    assert "Deployment failed" not in snap_before

    # explicit --force proceeds, archives the old baseline, records the event
    forced = run_rf(["baseline", "--force"], project)
    assert forced.returncode == 0
    assert "baseline.previous.json" in forced.stdout
    assert (project / ".regression-firewall" / "baseline.previous.json").is_file()
    snap = json.loads(
        (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    rebaseline = snap["provenance"]["rebaseline"]
    assert rebaseline["previous_verdict"] == "BLOCK"
    assert rebaseline["forced"] is True

    # the follow-up check passes but carries the trust warning everywhere
    check = run_rf(["check"], project)
    assert check.returncode == 0
    assert "BASELINE TRUST WARNING" in check.stdout
    report = read_report(project)
    assert report["baseline_trust_warning"] is True
    md = (project / ".regression-firewall" / "report.md").read_text(encoding="utf-8")
    assert "BASELINE TRUST WARNING" in md


def test_normal_rebaseline_after_pass_does_not_warn(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    run_rf(["check"], project, expect_exit=0)
    again = run_rf(["baseline"], project)
    assert again.returncode == 0
    assert "BASELINE TRUST WARNING" not in again.stdout
    check = run_rf(["check"], project)
    assert "BASELINE TRUST WARNING" not in check.stdout
    report = read_report(project)
    assert report["baseline_trust_warning"] is False


# ---------------------------------------------------------------------------
# P1.5 — extended secret redaction


def test_extended_secret_names_redacted(project, run_rf, write):
    app = '''from flask import Flask, jsonify
app = Flask(__name__)

@app.get("/users/42")
def all_secrets():
    return jsonify({
        "password": "p1", "passwd": "p2",
        "api_key": "k1", "apikey": "k2", "api-key": "k3",
        "access_token": "t1", "refresh_token": "t2", "session_token": "t3",
        "secret": "s1", "client_secret": "s2",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----",
        "bearer": "bearer-val-9", "jwt": "jwt-val-9",
        "nested": {"access_key": "ak1", "public_data": "visible"},
        "list_of_secrets": [{"credential": "c1"}],
        "normal_field": "keep me",
    })
'''
    serve = '''import os
from app import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("REGFW_SERVER_PORT", "8931")), debug=False)
'''
    write(project / "app.py", app)
    write(project / "serve.py", serve)
    write(project / ".regression-firewall.yml", """\
version: 1
surfaces:
  http:
    enabled: true
    server:
      command: ["python", "serve.py"]
    base_url: "http://127.0.0.1:{port}"
    probes:
      - id: "GET /users/42"
        method: GET
        path: /users/42
        headers: {"Authorization": "Bearer req-secret", "Cookie": "session=req-cookie"}
  cli: {enabled: false}
  public_api: {enabled: false}
""")
    run_rf(["baseline"], project, expect_exit=0)
    snap = (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    for secret in ("pw-val-1", "pw-val-2", "key-val-1", "key-val-2", "key-val-3",
                   "tok-val-1", "tok-val-2", "tok-val-3",
                   "sec-val-1", "sec-val-2", "BEGIN RSA PRIVATE KEY",
                   "bearer-val-9", "jwt-val-9", "akey-val-9", "cred-val-9",
                   "req-secret", "req-cookie"):
        assert secret not in snap, f"secret leaked: {secret}"
    body = json.loads(snap)["surfaces"]["http"][0]["data"]["body"]
    assert body["password"] == "<REDACTED>"
    assert body["private_key"] == "<REDACTED>"
    assert body["nested"]["access_key"] == "<REDACTED>"
    assert body["nested"]["public_data"] == "visible"
    assert body["list_of_secrets"][0]["credential"] == "<REDACTED>"
    assert body["normal_field"] == "keep me"


# ---------------------------------------------------------------------------
# P1.6 — no-change false-positive stability


def test_no_change_stability_cli_10x(project, run_rf, write):
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    false_positives = 0
    for _ in range(10):
        proc = run_rf(["check"], project)
        report = read_report(project)
        if proc.returncode != 0 or report["changes"]:
            false_positives += 1
    assert false_positives == 0, f"{false_positives}/10 no-change checks produced diffs"


def test_no_change_stability_http_10x(project, run_rf, write):
    """Timestamps, rotating UUID request-ids and fresh session cookies across
    10 unchanged checks must produce zero diffs."""
    server = '''\
import json, os, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Request-ID", str(uuid.uuid4()))
        self.send_header("Set-Cookie", f"session={uuid.uuid4().hex}; Path=/")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"id": 1, "created": "2026-01-01T10:00:00Z",
                         "ts": int(time.time()), "user_uuid": "550e8400-e29b-41d4-a716-446655440000"})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("REGFW_SERVER_PORT", "8931"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
'''
    write(project / "server.py", server)
    write(project / ".regression-firewall.yml", """\
version: 1
surfaces:
  http:
    enabled: true
    server:
      command: ["python", "server.py"]
    base_url: "http://127.0.0.1:{port}"
    probes:
      - id: "GET /x"
        method: GET
        path: /x
  cli: {enabled: false}
  public_api: {enabled: false}
""")
    run_rf(["baseline"], project, expect_exit=0)
    false_positives = 0
    details = []
    for i in range(10):
        proc = run_rf(["check"], project)
        report = read_report(project)
        if proc.returncode != 0 or report["changes"]:
            false_positives += 1
            details.append(str([(c["category"], c.get("path")) for c in report["changes"]]))
    assert false_positives == 0, f"{false_positives}/10: " + "; ".join(details)
