"""One-off authoring script that writes the 20 eval cases.

The generated files under evals/cases/ are the source of truth; this script
exists so the cases can be regenerated/adjusted without hand-editing 60 files.
Run from the repository root:  python evals/_author_cases.py
"""

from pathlib import Path

CASES = Path(__file__).resolve().parent / "cases"

HTTP_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: true
    server:
      command: ["python", "server.py"]
    base_url: "http://127.0.0.1:{port}"
    probes:
      - id: "POST /login"
        method: POST
        path: /login
        body: {"username": "alice", "password": "wrong"}
      - id: "GET /users/42"
        method: GET
        path: /users/42
  cli:
    enabled: false
  public_api:
    enabled: false
"""

MIXED_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: true
    server:
      command: ["python", "server.py"]
    base_url: "http://127.0.0.1:{port}"
    probes:
      - id: "POST /login"
        method: POST
        path: /login
        body: {"username": "alice", "password": "wrong"}
      - id: "GET /users/42"
        method: GET
        path: /users/42
  cli:
    enabled: true
    probes:
      - id: deploy
        command: ["python", "deploy.py"]
        files: ["receipt.txt"]
  public_api:
    enabled: false
"""

CLI_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: false
  cli:
    enabled: true
    probes:
      - id: deploy
        command: ["python", "deploy.py"]
        files: ["receipt.txt"]
  public_api:
    enabled: false
"""

API_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: false
  cli:
    enabled: false
  public_api:
    enabled: true
    probes:
      - id: samplelib
        module: samplelib
"""

LIB = '''class Client:
    def __init__(self, retries=3):
        self.retries = retries


class RetryPolicy:
    def __init__(self, attempts=5):
        self.attempts = attempts


def connect(host, port=5432):
    return (host, port)
'''

DEPLOY_PLAIN = '''import sys

def main():
    print("Deployment complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

DEPLOY_STARTING = '''import sys

def main():
    print("Starting deployment")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

DEPLOY_TEMP = '''import os, sys, tempfile

def main():
    cache = os.path.join(tempfile.gettempdir(), f"regfw-eval14-{os.getpid()}.tmp")
    with open(cache, "w") as f:
        f.write("cache")
    print("Deployment complete")
    print(f"cache: {cache}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''


def http_server(get_payload, extra_imports="", extra_headers=""):
    return f'''import json, os{extra_imports}
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json"):
        body = json.dumps(payload).encode() if isinstance(payload, (dict, list)) else str(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))){extra_headers}
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/users/42":
            self._send(200, {get_payload})
        else:
            self._send(404, {{"error": "not_found"}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path == "/login":
            self._send(401, {{"error": "invalid_credentials"}})
        else:
            self._send(404, {{"error": "not_found"}})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("REGFW_SERVER_PORT", "8931"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
'''


def block(text):
    """YAML literal block (stripped) for a multi-line find/replace string."""
    return "|-\n" + "".join(f"        {line}\n" for line in text.rstrip("\n").split("\n"))


def expect_block(entries, verdict):
    out = "expect:\n"
    if entries:
        out += "  changes:\n"
        for entry in entries:
            out += f"    - surface: {entry['surface']}\n"
            out += f'      target: "{entry["target"]}"\n'
            out += f"      category: {entry['category']}\n"
            if "path" in entry:
                out += f'      path: "{entry["path"]}"\n'
            out += f"      classification: {entry['classification']}\n"
            if "severity" in entry:
                out += f"      severity: {entry['severity']}\n"
    else:
        out += "  changes: []\n"
    out += f"  verdict: {verdict}\n"
    return out


def intent_block(task, entries):
    out = "intent:\n"
    out += f'  task: "{task}"\n'
    out += "  expected_changes:\n"
    for entry in entries:
        out += f"    - surface: {entry['surface']}\n"
        out += f'      target: "{entry["target"]}"\n'
        out += f"      category: {entry['category']}\n"
        if "path" in entry:
            out += f'      path: "{entry["path"]}"\n'
        if "note" in entry:
            out += f'      note: "{entry["note"]}"\n'
    return out


def write_case(slug, description, surface, before_files, case_extra="", mutations=None):
    case_dir = CASES / slug
    (case_dir / "before").mkdir(parents=True, exist_ok=True)
    for rel, content in before_files.items():
        path = case_dir / "before" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    mutations_yaml = ""
    if mutations:
        parts = ["mutations:\n"]
        for m in mutations:
            parts.append(f"    - file: {m['file']}\n")
            parts.append(f"      find: {block(m['find'])}")
            parts.append(f"      replace: {block(m['replace'])}")
        mutations_yaml = "".join(parts)
    case_yml = (
        f"name: {slug.split('_', 1)[1]}\n"
        f"surface: {surface}\n"
        f'description: "{description}"\n'
        + mutations_yaml
        + case_extra
    )
    (case_dir / "case.yml").write_text(case_yml, encoding="utf-8", newline="\n")


def mutation(file, find, replace):
    return {"file": file, "find": find, "replace": replace}


PLAIN_USER = '{"id": 42, "username": "alice", "email": "alice@example.com", "timestamp": "2026-01-01T10:00:00Z"}'
LOGIN_401 = 'self._send(401, {"error": "invalid_credentials"})'


def main():
    import shutil

    if CASES.exists():
        shutil.rmtree(CASES)

    # --- HTTP surface --------------------------------------------------------

    write_case(
        "01_http_status_401_to_400",
        "Login endpoint starts returning 400 instead of 401 for bad credentials.",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG, "server.py": http_server(PLAIN_USER)},
        mutations=[mutation("server.py", LOGIN_401,
                            'self._send(400, {"error": "invalid_credentials"})')],
        case_extra=expect_block(
            [{"surface": "http", "target": "POST /login", "category": "status_changed",
              "classification": "unexpected", "severity": "high"}],
            "BLOCK"),
    )

    write_case(
        "02_http_json_field_removed",
        "GET /users/42 response loses the email field.",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG, "server.py": http_server(PLAIN_USER)},
        mutations=[mutation(
            "server.py",
            '"username": "alice", "email": "alice@example.com",',
            '"username": "alice",')],
        case_extra=expect_block(
            [{"surface": "http", "target": "GET /users/42", "category": "field_removed",
              "path": "$.email", "classification": "unexpected", "severity": "high"}],
            "BLOCK"),
    )

    write_case(
        "03_http_json_field_added",
        "GET /users/42 response gains a debug field (additive, low severity).",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG, "server.py": http_server(PLAIN_USER)},
        mutations=[mutation(
            "server.py",
            '"username": "alice",',
            '"username": "alice", "debug": True,')],
        case_extra=expect_block(
            [{"surface": "http", "target": "GET /users/42", "category": "field_added",
              "path": "$.debug", "classification": "uncertain", "severity": "low"}],
            "PASS"),
    )

    write_case(
        "04_http_field_type_changed",
        "Response field age changes from number to string.",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG,
         "server.py": http_server('{"id": 42, "username": "alice", "age": 30, "timestamp": "2026-01-01T10:00:00Z"}')},
        mutations=[mutation("server.py", '"age": 30,', '"age": "30",')],
        case_extra=expect_block(
            [{"surface": "http", "target": "GET /users/42", "category": "field_type_changed",
              "path": "$.age", "classification": "unexpected", "severity": "medium"}],
            "REVIEW"),
    )

    write_case(
        "05_http_expected_field_rename",
        "username is renamed to display_name; the intent file records both sides.",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG, "server.py": http_server(PLAIN_USER)},
        mutations=[mutation(
            "server.py",
            '"username": "alice",',
            '"display_name": "alice",')],
        case_extra=intent_block(
            "Rename username to display_name in the user response.",
            [{"surface": "http", "target": "GET /users/42", "category": "field_removed",
              "path": "username", "note": "renamed to display_name"},
             {"surface": "http", "target": "GET /users/42", "category": "field_added",
              "path": "display_name", "note": "renamed from username"}])
        + expect_block(
            [{"surface": "http", "target": "GET /users/42", "category": "field_removed",
              "path": "$.username", "classification": "expected"},
             {"surface": "http", "target": "GET /users/42", "category": "field_added",
              "path": "$.display_name", "classification": "expected"}],
            "PASS"),
    )

    write_case(
        "06_http_timestamp_noise",
        "No code change; the response carries a live epoch timestamp that must normalize away.",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG,
         "server.py": http_server('{"id": 42, "username": "alice", "timestamp": int(time.time())}',
                                  extra_imports=", time")},
        mutations=[],
        case_extra=expect_block([], "PASS"),
    )

    write_case(
        "07_http_request_id_noise",
        "No code change; each response carries a fresh X-Request-ID that must normalize away.",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG,
         "server.py": http_server(PLAIN_USER, extra_imports=", uuid",
                                  extra_headers='\n        self.send_header("X-Request-ID", str(uuid.uuid4()))')},
        mutations=[],
        case_extra=expect_block([], "PASS"),
    )

    write_case(
        "08_http_header_change",
        "Cache-Control header flips from no-cache to max-age=300.",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG,
         "server.py": http_server(PLAIN_USER,
                                  extra_headers='\n        self.send_header("Cache-Control", "no-cache")')},
        mutations=[mutation(
            "server.py",
            'self.send_header("Cache-Control", "no-cache")',
            'self.send_header("Cache-Control", "max-age=300")')],
        case_extra=expect_block(
            [{"surface": "http", "target": "GET /users/42", "category": "header_changed",
              "path": "cache-control", "classification": "uncertain", "severity": "low"},
             {"surface": "http", "target": "POST /login", "category": "header_changed",
              "path": "cache-control", "classification": "uncertain", "severity": "low"}],
            "REVIEW"),
    )

    write_case(
        "09_http_content_type_change",
        "GET /users/42 switches from a JSON payload to plain text.",
        "http",
        {".regression-firewall.yml": HTTP_CONFIG, "server.py": http_server(PLAIN_USER)},
        mutations=[mutation(
            "server.py",
            'self._send(200, ' + PLAIN_USER + ')',
            'self._send(200, "user 42: alice", "text/plain")')],
        case_extra=expect_block(
            [{"surface": "http", "target": "GET /users/42", "category": "content_type_changed",
              "classification": "unexpected", "severity": "medium"}],
            "REVIEW"),
    )

    # --- CLI surface ---------------------------------------------------------

    write_case(
        "10_cli_exit_code_regression",
        "deploy.py starts failing: exit 0 -> 1 and the success message becomes a failure message.",
        "cli",
        {".regression-firewall.yml": CLI_CONFIG, "deploy.py": DEPLOY_PLAIN},
        mutations=[mutation(
            "deploy.py",
            'print("Deployment complete")\n    return 0',
            'print("Deployment failed")\n    return 1')],
        case_extra=expect_block(
            [{"surface": "cli", "target": "deploy", "category": "exit_code_changed",
              "classification": "unexpected", "severity": "high"},
             {"surface": "cli", "target": "deploy", "category": "stdout_changed",
              "classification": "uncertain", "severity": "low"}],
            "BLOCK"),
    )

    write_case(
        "11_cli_stdout_change",
        "The success message text changes; exit code stays 0.",
        "cli",
        {".regression-firewall.yml": CLI_CONFIG, "deploy.py": DEPLOY_PLAIN},
        mutations=[mutation(
            "deploy.py",
            'print("Deployment complete")',
            'print("Deployment finished successfully")')],
        case_extra=expect_block(
            [{"surface": "cli", "target": "deploy", "category": "stdout_changed",
              "classification": "uncertain", "severity": "low"}],
            "REVIEW"),
    )

    write_case(
        "12_cli_stderr_change",
        "A deprecation warning appears on stderr; stdout and exit code unchanged.",
        "cli",
        {".regression-firewall.yml": CLI_CONFIG, "deploy.py": DEPLOY_STARTING},
        mutations=[mutation(
            "deploy.py",
            'print("Starting deployment")\n    return 0',
            'print("Starting deployment")\n    print("warning: the --force flag is deprecated", file=sys.stderr)\n    return 0')],
        case_extra=expect_block(
            [{"surface": "cli", "target": "deploy", "category": "stderr_changed",
              "classification": "uncertain", "severity": "low"}],
            "REVIEW"),
    )

    write_case(
        "13_cli_generated_file",
        "deploy.py starts writing receipt.txt, which is on the watch list.",
        "cli",
        {".regression-firewall.yml": CLI_CONFIG, "deploy.py": DEPLOY_PLAIN},
        mutations=[mutation(
            "deploy.py",
            'print("Deployment complete")\n    return 0',
            'print("Deployment complete")\n    with open("receipt.txt", "w") as f:\n        f.write("receipt ok")\n    return 0')],
        case_extra=expect_block(
            [{"surface": "cli", "target": "deploy", "category": "file_created",
              "path": "receipt.txt", "classification": "uncertain", "severity": "medium"}],
            "REVIEW"),
    )

    write_case(
        "14_cli_temp_file_noise",
        "No code change; the script prints a temp path containing a fresh PID that must normalize away.",
        "cli",
        {".regression-firewall.yml": CLI_CONFIG, "deploy.py": DEPLOY_TEMP},
        mutations=[],
        case_extra=expect_block([], "PASS"),
    )

    # --- Public API surface ---------------------------------------------------

    def lib_case(slug, description, mutations, case_extra):
        write_case(slug, description, "public_api",
                   {".regression-firewall.yml": API_CONFIG,
                    "samplelib/__init__.py": LIB},
                   mutations=mutations, case_extra=case_extra)

    lib_case(
        "15_api_symbol_removed",
        "Public class RetryPolicy is removed from the package.",
        [mutation("samplelib/__init__.py",
                  "class RetryPolicy:\n    def __init__(self, attempts=5):\n        self.attempts = attempts\n\n\n",
                  "")],
        expect_block(
            [{"surface": "public_api", "target": "samplelib.RetryPolicy",
              "category": "symbol_removed", "classification": "unexpected",
              "severity": "critical"}],
            "BLOCK"),
    )

    lib_case(
        "16_api_symbol_added",
        "A new public function ping is added (additive, informational).",
        [mutation("samplelib/__init__.py",
                  "def connect(host, port=5432):\n    return (host, port)",
                  "def connect(host, port=5432):\n    return (host, port)\n\n\ndef ping():\n    return \"pong\"")],
        expect_block(
            [{"surface": "public_api", "target": "samplelib.ping",
              "category": "symbol_added", "classification": "uncertain",
              "severity": "info"}],
            "PASS"),
    )

    lib_case(
        "17_api_signature_changed",
        "connect() drops the default for port and gains a timeout parameter.",
        [mutation("samplelib/__init__.py",
                  "def connect(host, port=5432):",
                  "def connect(host, port, timeout=30):")],
        expect_block(
            [{"surface": "public_api", "target": "samplelib.connect",
              "category": "signature_changed", "classification": "unexpected",
              "severity": "medium"}],
            "REVIEW"),
    )

    lib_case(
        "18_api_expected_change",
        "RetryPolicy removal is intentional and recorded in the intent file.",
        [mutation("samplelib/__init__.py",
                  "class RetryPolicy:\n    def __init__(self, attempts=5):\n        self.attempts = attempts\n\n\n",
                  "")],
        intent_block(
            "Drop RetryPolicy; users should use Client-level retries.",
            [{"surface": "public_api", "target": "samplelib.RetryPolicy",
              "category": "symbol_removed", "note": "intentional removal"}])
        + expect_block(
            [{"surface": "public_api", "target": "samplelib.RetryPolicy",
              "category": "symbol_removed", "classification": "expected"}],
            "PASS"),
    )

    # --- Mixed ------------------------------------------------------------------

    write_case(
        "19_multiple_regressions",
        "One task breaks three behaviors: login status, user payload field, and deploy exit code.",
        "mixed",
        {".regression-firewall.yml": MIXED_CONFIG,
         "server.py": http_server(PLAIN_USER),
         "deploy.py": DEPLOY_PLAIN},
        mutations=[
            mutation("server.py", LOGIN_401,
                     'self._send(400, {"error": "invalid_credentials"})'),
            mutation("server.py",
                     '"username": "alice", "email": "alice@example.com",',
                     '"username": "alice",'),
            mutation("deploy.py",
                     'print("Deployment complete")\n    return 0',
                     'print("Deployment failed")\n    return 1'),
        ],
        case_extra=expect_block(
            [{"surface": "http", "target": "POST /login", "category": "status_changed",
              "classification": "unexpected", "severity": "high"},
             {"surface": "http", "target": "GET /users/42", "category": "field_removed",
              "path": "$.email", "classification": "unexpected", "severity": "high"},
             {"surface": "cli", "target": "deploy", "category": "exit_code_changed",
              "classification": "unexpected", "severity": "high"},
             {"surface": "cli", "target": "deploy", "category": "stdout_changed",
              "classification": "uncertain", "severity": "low"}],
            "BLOCK"),
    )

    write_case(
        "20_no_regression",
        "No code change and deterministic output; the tool must report a clean PASS.",
        "cli",
        {".regression-firewall.yml": CLI_CONFIG, "deploy.py": DEPLOY_PLAIN},
        mutations=[],
        case_extra=expect_block([], "PASS"),
    )


if __name__ == "__main__":
    main()
    print("eval cases written to", CASES)
