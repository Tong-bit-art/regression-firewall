"""End-to-end: convention-based app detection and `discover --emit-probes`
against a real Flask app (flask is a dev dependency)."""

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


@app.route("/users/<int:uid>")
def user(uid):
    return jsonify(uid=uid)
"""


def _write_app(tmp_path):
    (tmp_path / "app.py").write_text(FLASK_APP, encoding="utf-8")


def test_discover_lists_app_candidates(tmp_path, capsys):
    _write_app(tmp_path)
    assert cli.main(["--project", str(tmp_path), "discover"]) == 0
    out = capsys.readouterr().out
    assert "detected app candidate(s) by convention" in out
    assert "app:app" in out
    assert "flask" in out


def test_discover_emit_probes_autodetected(tmp_path, capsys):
    _write_app(tmp_path)
    assert cli.main(["--project", str(tmp_path), "discover", "--emit-probes"]) == 0
    captured = capsys.readouterr()
    assert "auto-detected app: app:app" in captured.err
    assert "id: GET /" in captured.out
    assert "id: GET /about" in captured.out
    # parameterized route is excluded and reported in the notes
    assert "/users/<int:uid>" not in captured.out
    assert "parameterized route(s) excluded" in captured.err


def test_discover_emit_probes_explicit_spec(tmp_path, capsys):
    _write_app(tmp_path)
    code = cli.main(["--project", str(tmp_path), "discover", "--emit-probes", "app:app"])
    assert code == 0
    out = capsys.readouterr().out
    assert "id: GET /about" in out


def test_discover_emit_probes_no_candidates_is_error(tmp_path, capsys):
    (tmp_path / "plain.py").write_text("print('hi')\n", encoding="utf-8")
    code = cli.main(["--project", str(tmp_path), "discover", "--emit-probes"])
    assert code == cli.EXIT_ERROR
    assert "no FastAPI/Flask/Starlette app" in capsys.readouterr().err


def test_discover_emit_probes_bad_spec_is_error(tmp_path, capsys):
    _write_app(tmp_path)
    code = cli.main(["--project", str(tmp_path), "discover",
                     "--emit-probes", "app:app:extra"])
    assert code == cli.EXIT_ERROR
    assert "invalid app spec" in capsys.readouterr().err


def test_discover_emit_probes_broken_app_is_error(tmp_path, capsys):
    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\nraise SystemExit(3)\n",
        encoding="utf-8",
    )
    code = cli.main(["--project", str(tmp_path), "discover",
                     "--emit-probes", "app:app"])
    assert code == cli.EXIT_ERROR
    assert "route discovery failed" in capsys.readouterr().err
