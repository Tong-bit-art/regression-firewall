"""Release-audit regression tests (C1, H1, H2, M1, M2, L5 fixes)."""

import json

from _fixtures import CLI_CONFIG, DEPLOY_PLAIN, read_report


PRIVACY_APP = '''from flask import Flask, jsonify, request

app = Flask(__name__)

@app.get("/users/42")
def echo():
    auth = request.headers.get("Authorization", "none")
    resp = jsonify({"id": 42, "auth_seen": auth, "password": "hunter2",
                    "api_key": "sk-live-123", "session_token": "tok-abc"})
    resp.set_cookie("session", "s3cret-session-value")
    resp.set_cookie("theme", "dark")
    resp.headers["X-Auth-Token"] = "resp-secret-token"
    return resp
'''

PRIVACY_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: true
    server:
      command: ["python", "serve.py"]
    base_url: "http://127.0.0.1:{port}"
    ready_path: "/users/42"
    probes:
      - id: "GET /users/42"
        method: GET
        path: /users/42
        headers: {"Authorization": "Bearer sk-live-topsecret"}
  cli: {enabled: false}
  public_api: {enabled: false}
"""

PRIVACY_SERVE = """\
import os
import socket
socket.getfqdn = lambda *a, **k: "127.0.0.1"  # skip reverse DNS (hangs on macOS CI)
from app import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("REGFW_SERVER_PORT", "8931")), debug=False)
"""


def test_snapshot_secrets_redacted(project, run_rf, write):
    """C1: secrets must be masked in stored snapshots, not just in reports."""
    write(project / "app.py", PRIVACY_APP)
    write(project / "serve.py", PRIVACY_SERVE)
    write(project / ".regression-firewall.yml", PRIVACY_CONFIG)

    run_rf(["baseline"], project, expect_exit=0)
    snap = (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    for secret in ("sk-live-topsecret", "hunter2", "sk-live-123", "tok-abc",
                   "s3cret-session-value", "Bearer sk-live", "resp-secret-token"):
        assert secret not in snap, f"secret leaked into snapshot: {secret}"
    data = json.loads(snap)
    capture = data["surfaces"]["http"][0]["data"]
    assert capture["headers"]["x-auth-token"] == "<REDACTED>"
    assert capture["cookies"]["session"] == "<REDACTED>"
    assert capture["cookies"]["theme"] == "<REDACTED>"
    assert capture["body"]["password"] == "<REDACTED>"
    assert capture["body"]["api_key"] == "<REDACTED>"
    assert capture["body"]["auth_seen"] == "<REDACTED>"
    # non-secret body data stays intact so behavior diffs remain meaningful
    assert capture["body"]["id"] == 42

    # the check loop still works on redacted snapshots (rotation is invisible)
    run_rf(["check"], project, expect_exit=0)


def test_snapshot_redaction_can_be_disabled(project, run_rf, write):
    write(project / "app.py", PRIVACY_APP)
    write(project / "serve.py", PRIVACY_SERVE)
    write(project / ".regression-firewall.yml",
          PRIVACY_CONFIG + "redaction:\n  secrets: false\n")
    run_rf(["baseline"], project, expect_exit=0)
    snap = (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    assert "s3cret-session-value" in snap  # explicit opt-out is honored


def test_same_size_same_second_edit_is_captured(project, run_rf, write):
    """H1: stale __pycache__ must never produce a false PASS. The mutation
    keeps the file size identical (complete->fa1lure8, return 0->1) and runs
    immediately after the baseline, hitting the same-second pyc race."""
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    baseline_src = (project / "deploy.py").read_text(encoding="utf-8")
    mutated_src = baseline_src.replace('"Deployment complete"', '"Deployment fa1lure8"') \
                              .replace("    return 0", "    return 1")
    assert len(mutated_src) == len(baseline_src) and mutated_src != baseline_src
    for attempt in range(5):
        write(project / "deploy.py", baseline_src)
        # --force: the previous attempt's check reported BLOCK, so the
        # re-baseline guard correctly demands explicit acknowledgment.
        assert run_rf(["baseline", "--force"], project).returncode == 0
        write(project / "deploy.py", mutated_src)
        proc = run_rf(["check"], project)
        report = read_report(project)
        assert proc.returncode == 3, f"attempt {attempt}: {proc.stdout}"
        assert ("cli", "deploy", "exit_code_changed", "unexpected", "high") in {
            (c["surface"], c["target"], c["category"], c["classification"], c["severity"])
            for c in report["changes"]
        }


def test_ignore_json_paths_suppress_structural_changes(project, run_rf, write):
    """H2: ignore.json_paths must suppress field_added/removed/value changes
    at the ignored path, not only value normalization."""
    write(project / "server.py", '''\
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class QuietHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        import socketserver
        socketserver.TCPServer.server_bind(self)

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"id": 1, "meta": {"debug_trace": {"seed": "a"}}, "keep": "x"})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("REGFW_SERVER_PORT", "8931"))
    QuietHTTPServer(("127.0.0.1", port), Handler).serve_forever()
''')
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
ignore:
  headers: [date, content-length]
  json_paths: ["*.debug_trace"]
""")
    run_rf(["baseline"], project, expect_exit=0)
    write(project / "server.py", '''\
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class QuietHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        import socketserver
        socketserver.TCPServer.server_bind(self)

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"id": 1, "meta": {}, "keep": "y"})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("REGFW_SERVER_PORT", "8931"))
    QuietHTTPServer(("127.0.0.1", port), Handler).serve_forever()
''')
    proc = run_rf(["check"], project)
    report = read_report(project)
    paths = [c.get("path") for c in report["changes"]]
    assert not any(p and "debug_trace" in p for p in paths), report["changes"]
    # non-ignored changes still reported (keep: x -> y is a value change)
    assert any(c["category"] == "value_changed" and c["path"] == "$.keep" for c in report["changes"])


def test_binary_body_change_detected(project, run_rf, write):
    """M1: binary responses store their size so content changes surface."""
    server_v1 = '''\
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class QuietHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        import socketserver
        socketserver.TCPServer.server_bind(self)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"\\x00\\x01BINARY"
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("REGFW_SERVER_PORT", "8931"))
    QuietHTTPServer(("127.0.0.1", port), Handler).serve_forever()
'''
    server_v2 = server_v1.replace('b"\\x00\\x01BINARY"', 'b"\\x00\\x01BINARY-LONGER"')
    write(project / "server.py", server_v1)
    write(project / ".regression-firewall.yml", """\
version: 1
surfaces:
  http:
    enabled: true
    server:
      command: ["python", "server.py"]
    base_url: "http://127.0.0.1:{port}"
    probes:
      - id: "GET /blob"
        method: GET
        path: /blob
  cli: {enabled: false}
  public_api: {enabled: false}
""")
    run_rf(["baseline"], project, expect_exit=0)
    write(project / "server.py", server_v2)
    run_rf(["check"], project)
    report = read_report(project)
    assert any(c["category"] == "value_changed" and c["path"] == "$body" for c in report["changes"]), \
        report["changes"]


def test_explicit_intent_path_must_exist(project, run_rf, write):
    """M2: a typo'd --intent path is an error, not a silent empty intent."""
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    proc = run_rf(["check", "--intent", "does-not-exist.json"], project)
    assert proc.returncode == 70
    assert "intent file not found" in proc.stderr
    # the default (missing) intent file is still fine
    run_rf(["check"], project, expect_exit=0)


def test_wildcard_intent_warns(project, run_rf, write):
    """L5: an all-wildcard intent entry must announce itself in the report."""
    write(project / "deploy.py", DEPLOY_PLAIN)
    write(project / ".regression-firewall.yml", CLI_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    write(project / ".regression-firewall" / "intent.json", json.dumps({
        "schema_version": 1,
        "task": "sloppy intent",
        "expected_changes": [{"surface": "*", "target": "*", "category": "*"}],
    }))
    proc = run_rf(["check"], project)
    assert "all fields wildcarded" in proc.stdout
