import json


HTTP_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: true
    server:
      command: ["python", "server.py"]
    base_url: "http://127.0.0.1:{port}"
    probes:
      - id: "GET /user"
        method: GET
        path: /user
  cli:
    enabled: false
  public_api:
    enabled: false
"""

SERVER_V1 = """\
import json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class QuietHTTPServer(ThreadingHTTPServer):
    # skip the reverse-DNS lookup in HTTPServer.server_bind (hangs on hosts
    # with broken resolvers, e.g. GitHub macOS runners)
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
        if self.path == "/user":
            self._send(200, {
                "id": 1,
                "name": "alice",
                "email": "alice@example.com",
                "timestamp": int(time.time()),
            })
        else:
            self._send(404, {"error": "not_found"})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("REGFW_SERVER_PORT", "8931"))
    QuietHTTPServer(("127.0.0.1", port), Handler).serve_forever()
"""


def read_report(project):
    return json.loads(
        (project / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )


def test_http_surface_field_removed_blocked(project, run_rf, write):
    write(project / "server.py", SERVER_V1)
    write(project / ".regression-firewall.yml", HTTP_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)

    # remove a response field -> HIGH regression
    mutated = SERVER_V1.replace(
        '                "email": "alice@example.com",\n', ""
    )
    assert mutated != SERVER_V1
    write(project / "server.py", mutated)
    proc = run_rf(["check"], project)
    assert proc.returncode == 3, proc.stdout  # BLOCK
    report = read_report(project)
    assert report["verdict"] == "BLOCK"
    assert ("field_removed", "unexpected") in {
        (c["category"], c["classification"]) for c in report["changes"]
    }


def test_http_surface_timestamp_noise_ignored(project, run_rf, write):
    write(project / "server.py", SERVER_V1)
    write(project / ".regression-firewall.yml", HTTP_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)
    # same server code: only the live timestamp value differs between runs
    proc = run_rf(["check"], project)
    assert proc.returncode == 0, proc.stdout
    report = read_report(project)
    assert report["changes"] == []


def test_http_surface_rename_with_intent_passes(project, run_rf, write):
    write(project / "server.py", SERVER_V1)
    write(project / ".regression-firewall.yml", HTTP_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)

    mutated = SERVER_V1.replace('"name": "alice",', '"display_name": "alice",')
    write(project / "server.py", mutated)
    intent = {
        "schema_version": 1,
        "task": "Rename name to display_name.",
        "expected_changes": [
            {"surface": "http", "target": "GET /user", "category": "field_removed",
             "path": "name", "note": "renamed"},
            {"surface": "http", "target": "GET /user", "category": "field_added",
             "path": "display_name", "note": "renamed"},
        ],
    }
    write(project / ".regression-firewall" / "intent.json", json.dumps(intent, indent=2))
    proc = run_rf(["check"], project)
    assert proc.returncode == 0, proc.stdout
    report = read_report(project)
    assert report["verdict"] == "PASS"
    assert len(report["changes"]) == 2
    assert all(c["classification"] == "expected" for c in report["changes"])


def test_http_surface_server_not_startable(project, run_rf, write):
    write(project / "server.py", "import sys\nsys.exit(2)\n")
    write(project / ".regression-firewall.yml", HTTP_CONFIG)
    proc = run_rf(["baseline"], project)
    assert proc.returncode == 0  # baseline still writes a snapshot
    assert "HTTP server could not be started" in proc.stdout
    snapshot = json.loads(
        (project / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    assert snapshot["surfaces"]["http"][0]["ok"] is False


def test_http_server_cwd_config(tmp_path, run_rf, write):
    """The managed server must honor surfaces.http.server.cwd (relative to
    the project root) — needed when the app package resolves from a parent
    directory (e.g. flaskr's `--app flaskr` from examples/tutorial)."""
    write(tmp_path / "app" / "server.py", """\
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class QuietHTTPServer(ThreadingHTTPServer):
    def server_bind(self):
        import socketserver
        socketserver.TCPServer.server_bind(self)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("REGFW_SERVER_PORT", "8931"))
    QuietHTTPServer(("127.0.0.1", port), Handler).serve_forever()
""")
    write(tmp_path / "app" / ".regression-firewall.yml", """\
version: 1
surfaces:
  http:
    enabled: true
    server:
      command: ["python", "server.py"]
      cwd: "."
    base_url: "http://127.0.0.1:{port}"
    probes:
      - id: "GET /x"
        method: GET
        path: /x
  cli: {enabled: false}
  public_api: {enabled: false}
""")
    # project root is the PARENT; the app lives one level down and the config
    # sits there too — server.cwd resolves relative to the project root
    proc = run_rf(["--project", str(tmp_path / "app"), "baseline"], tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    snap = json.loads(
        (tmp_path / "app" / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    assert snap["surfaces"]["http"][0]["ok"] is True
