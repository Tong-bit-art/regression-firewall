"""End-to-end: `init` auto-configures probes from a detected app and the
scaffolded config actually works (baseline + check against the managed
server). Falls back to the commented template when nothing can be verified."""

import json
import sys

import pytest

from regression_firewall import cli

FLASK_APP = """\\
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return jsonify(ok=True)


@app.route("/about")
def about():
    return jsonify(about=True)
"""


def _flask_project(tmp_path):
    (tmp_path / "app.py").write_text(FLASK_APP, encoding="utf-8")


def test_init_autowires_flask_app(tmp_path):
    _flask_project(tmp_path)
    assert cli.main(["--project", str(tmp_path), "init"]) == 0
    config = (tmp_path / ".regression-firewall.yml").read_text(encoding="utf-8")
    # probes generated from the app's real routes
    assert "- id: GET /" in config
    assert "- id: GET /about" in config
    # managed Flask server + {port} base_url + ready_path
    assert 'command: ["python", "-m", "flask", "--app", "app:app", "run"' in config
    assert 'base_url: "http://127.0.0.1:{port}"' in config
    assert 'ready_path: "/"' in config
    # the public_api probe for the detected package
    # (no package here, so public_api stays commented)


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="the managed `flask run` server is werkzeug's, whose server_bind "
           "calls socket.getfqdn — ~35s reverse-DNS hang on macOS CI runners "
           "(exceeds the 30s ready timeout); the tool's own ManagedServer "
           "overrides this, third-party servers cannot be patched from here",
)
def test_init_autowired_config_runs_end_to_end(tmp_path):
    _flask_project(tmp_path)
    assert cli.main(["--project", str(tmp_path), "init"]) == 0
    # the scaffolded config must load and capture cleanly, twice
    assert cli.main(["--project", str(tmp_path), "baseline"]) == 0
    snapshot = json.loads(
        (tmp_path / ".regression-firewall" / "baseline.json").read_text(encoding="utf-8")
    )
    assert "http" in snapshot["surfaces"]
    assert len(snapshot["surfaces"]["http"]) == 2
    assert all(c["ok"] for c in snapshot["surfaces"]["http"])
    assert cli.main(["--project", str(tmp_path), "check"]) == cli.EXIT_OK


def test_init_without_app_keeps_template(tmp_path):
    (tmp_path / "plain.py").write_text("print('hi')\n", encoding="utf-8")
    assert cli.main(["--project", str(tmp_path), "init"]) == 0
    config = (tmp_path / ".regression-firewall.yml").read_text(encoding="utf-8")
    assert "probes: []" in config  # commented template untouched
    assert "id: GET /" not in config


def test_init_broken_app_falls_back_to_template(tmp_path):
    # the module imports fastapi (statically detected) but fastapi is not
    # installed -> route discovery fails -> template fallback, loud note
    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    assert cli.main(["--project", str(tmp_path), "init"]) == 0
    config = (tmp_path / ".regression-firewall.yml").read_text(encoding="utf-8")
    assert "probes: []" in config
