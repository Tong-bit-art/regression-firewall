import json

import pytest

from regression_firewall.cli import main
from regression_firewall.config.loader import load_config
from regression_firewall.config.openapi import (
    load_openapi_document,
    probes_from_openapi,
)
from regression_firewall.config.schema import ConfigError

SAMPLE = """
openapi: "3.0.3"
info:
  title: Sample API
  version: "1.0"
paths:
  /health:
    get:
      operationId: health
  /users:
    post:
      requestBody:
        content:
          application/json:
            example: {"name": "alice", "roles": ["admin"]}
  /users/{id}:
    get:
      parameters:
        - name: id
          in: path
          required: true
          schema: {type: integer}
  /orders:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                sku: {type: string}
                qty: {type: integer}
                price: {type: number}
                gift: {type: boolean}
                tags:
                  type: array
                  items: {type: string}
"""


@pytest.fixture
def doc_path(tmp_path):
    path = tmp_path / "openapi.yaml"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def test_generates_probes_in_document_order(doc_path):
    doc = load_openapi_document(doc_path)
    probes, warnings = probes_from_openapi(doc)
    assert [p.id for p in probes] == [
        "GET /health", "POST /users", "GET /users/1", "POST /orders",
    ]
    # {id} had no --set value → defaulted with a warning
    assert any("{id}" in w and "'1'" in w for w in warnings)


def test_example_body_wins(doc_path):
    doc = load_openapi_document(doc_path)
    probes, _ = probes_from_openapi(doc)
    post_users = next(p for p in probes if p.id == "POST /users")
    assert post_users.body == {"name": "alice", "roles": ["admin"]}


def test_schema_skeleton_body_is_deterministic(doc_path):
    doc = load_openapi_document(doc_path)
    probes, _ = probes_from_openapi(doc)
    post_orders = next(p for p in probes if p.id == "POST /orders")
    assert post_orders.body == {
        "sku": "", "qty": 0, "price": 0.0, "gift": False, "tags": [""],
    }


def test_set_values_replace_params(doc_path):
    doc = load_openapi_document(doc_path)
    probes, warnings = probes_from_openapi(doc, set_values={"id": "42"})
    assert "GET /users/42" in [p.id for p in probes]
    assert not any("{id}" in w for w in warnings)


def test_methods_filter(doc_path):
    doc = load_openapi_document(doc_path)
    probes, _ = probes_from_openapi(doc, methods=["post"])
    assert [p.id for p in probes] == ["POST /users", "POST /orders"]


def test_swagger2_rejected():
    with pytest.raises(ConfigError, match="Swagger 2"):
        probes_from_openapi({"swagger": "2.0", "paths": {"/x": {"get": {}}}})


def test_non_openapi_rejected():
    with pytest.raises(ConfigError, match="not an OpenAPI"):
        probes_from_openapi({"info": {"title": "nope"}})


def test_no_paths_rejected():
    with pytest.raises(ConfigError, match="no 'paths'"):
        probes_from_openapi({"openapi": "3.0.3"})


def test_filter_matching_nothing_rejected(doc_path):
    doc = load_openapi_document(doc_path)
    with pytest.raises(ConfigError, match="no HTTP operations"):
        probes_from_openapi(doc, methods=["delete"])


def test_collapse_collision_keeps_first_with_warning():
    doc = {
        "openapi": "3.0.3",
        "paths": {
            "/users/{id}": {"get": {}},
            "/users/{name}": {"get": {}},
        },
    }
    probes, warnings = probes_from_openapi(doc, set_values={"id": "1", "name": "1"})
    assert [p.id for p in probes] == ["GET /users/1"]
    assert any("more than once" in w for w in warnings)


def test_missing_file_is_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_openapi_document(tmp_path / "missing.yaml")


def test_invalid_json_rejected(tmp_path):
    path = tmp_path / "openapi.json"
    path.write_text("{nope", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid JSON"):
        load_openapi_document(path)


def test_json_document_accepted(tmp_path):
    path = tmp_path / "openapi.json"
    path.write_text(json.dumps({
        "openapi": "3.0.3",
        "paths": {"/ping": {"get": {}}},
    }), encoding="utf-8")
    doc = load_openapi_document(path)
    probes, _ = probes_from_openapi(doc)
    assert [p.id for p in probes] == ["GET /ping"]


# -- config integration ----------------------------------------------------------


def _write_config(tmp_path, extra=""):
    (tmp_path / ".regression-firewall.yml").write_text(f"""
version: 1
surfaces:
  http:
    base_url: "http://127.0.0.1:8000"
{extra}
""", encoding="utf-8")


def test_load_config_merges_openapi_probes(tmp_path, doc_path):
    _write_config(tmp_path, extra="""    openapi:
      file: openapi.yaml
      set: {id: "7"}
""")
    cfg, warnings, _ = load_config(tmp_path)
    ids = [p.id for p in cfg.http.probes]
    assert "GET /users/7" in ids
    assert len(ids) == 4
    assert not any("{id}" in w for w in warnings)


def test_load_config_explicit_probe_wins(tmp_path, doc_path):
    _write_config(tmp_path, extra="""    openapi:
      file: openapi.yaml
    probes:
      - id: "GET /health"
        method: GET
        path: /custom-health
""")
    cfg, warnings, _ = load_config(tmp_path)
    health = [p for p in cfg.http.probes if p.id == "GET /health"]
    assert len(health) == 1
    assert health[0].path == "/custom-health"
    assert any("explicit probe" in w for w in warnings)


def test_load_config_missing_openapi_file(tmp_path):
    _write_config(tmp_path, extra="""    openapi:
      file: missing.yaml
""")
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path)


def test_import_openapi_cli(tmp_path, doc_path, capsys):
    exit_code = main(["--project", str(tmp_path), "import-openapi", "openapi.yaml",
                      "--set", "id=42"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "id: GET /users/42" in out
    assert "body:" in out


def test_import_openapi_cli_bad_set(tmp_path, doc_path):
    exit_code = main(["--project", str(tmp_path), "import-openapi", "openapi.yaml",
                      "--set", "novalue"])
    assert exit_code == 70


def test_import_openapi_cli_bad_method(tmp_path, doc_path):
    exit_code = main(["--project", str(tmp_path), "import-openapi", "openapi.yaml",
                      "--methods", "FETCH"])
    assert exit_code == 70
