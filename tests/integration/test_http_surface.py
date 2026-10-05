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
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
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
