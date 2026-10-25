from regression_firewall.discovery.appdetect import (
    _path_to_module,
    detect_app_candidates,
    probes_from_routes,
    split_routes,
)


def _write(tmp_path, rel, text):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_detect_fastapi_in_app_py(tmp_path):
    _write(tmp_path, "app.py",
           "from fastapi import FastAPI\n\napp = FastAPI()\n")
    candidates = detect_app_candidates(tmp_path)
    assert len(candidates) == 1
    c = candidates[0]
    assert (c.module, c.attr, c.framework, c.line) == ("app", "app", "fastapi", 3)
    assert c.spec == "app:app"


def test_detect_flask_nested_module_derivation(tmp_path):
    _write(tmp_path, "api/main.py",
           "from flask import Flask\napp = Flask(__name__)\n")
    candidates = detect_app_candidates(tmp_path)
    assert len(candidates) == 1
    assert candidates[0].module == "api.main"
    assert candidates[0].framework == "flask"


def test_ranking_prefers_app_py_over_main_py(tmp_path):
    _write(tmp_path, "app.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    _write(tmp_path, "main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    candidates = detect_app_candidates(tmp_path)
    assert candidates[0].file == "app.py"
    assert candidates[1].file == "main.py"


def test_ranking_prefers_app_variable_name(tmp_path):
    # neither filename is preferred, so the attr bonus decides
    _write(tmp_path, "server_a.py", "from flask import Flask\napplication = Flask(__name__)\n")
    _write(tmp_path, "server_b.py", "from flask import Flask\napp = Flask(__name__)\n")
    candidates = detect_app_candidates(tmp_path)
    assert candidates[0].file == "server_b.py"


def test_skips_venv_and_hidden_dirs(tmp_path):
    _write(tmp_path, ".venv/lib/app.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    _write(tmp_path, "venv/app.py", "from fastapi import FastAPI\napp = Flask=__import__('flask')\n")
    _write(tmp_path, "node_modules/x.py", "from fastapi import FastAPI\napp = FastAPI()\n")
    assert detect_app_candidates(tmp_path) == []


def test_no_framework_import_no_candidates(tmp_path):
    _write(tmp_path, "app.py", "app = FastAPI()\n")  # constructor without import
    assert detect_app_candidates(tmp_path) == []


def test_non_app_flask_import_ignored(tmp_path):
    _write(tmp_path, "util.py", "from flask import jsonify\n\ndef make():\n    return jsonify({})\n")
    assert detect_app_candidates(tmp_path) == []


def test_module_name_for_package_init(tmp_path):
    assert _path_to_module(__import__("pathlib").Path("pkg/__init__.py")) == "pkg"
    assert _path_to_module(__import__("pathlib").Path("pkg/sub/mod.py")) == "pkg.sub.mod"
    assert _path_to_module(__import__("pathlib").Path("app.py")) == "app"


def test_split_routes_concrete_vs_parameterized():
    routes = [
        {"methods": ["GET"], "path": "/health"},
        {"methods": ["GET"], "path": "/users/{user_id}"},       # FastAPI
        {"methods": ["POST"], "path": "/posts/<int:post_id>"},  # Flask
        {"methods": ["GET"], "path": "/about"},
    ]
    concrete, parameterized = split_routes(routes)
    assert [r["path"] for r in concrete] == ["/health", "/about"]
    assert {r["path"] for r in parameterized} == {"/users/{user_id}", "/posts/<int:post_id>"}


def test_probes_from_routes_expands_methods_and_filters():
    routes = [
        {"methods": ["GET"], "path": "/b"},
        {"methods": ["GET", "POST"], "path": "/a"},
        {"methods": ["HEAD", "OPTIONS"], "path": "/a"},
        {"methods": ["GET"], "path": "/c"},
    ]
    probes = probes_from_routes(routes)
    assert probes == [
        {"id": "GET /a", "method": "GET", "path": "/a"},
        {"id": "POST /a", "method": "POST", "path": "/a"},
        {"id": "GET /b", "method": "GET", "path": "/b"},
        {"id": "GET /c", "method": "GET", "path": "/c"},
    ]
