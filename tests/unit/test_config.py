import pytest

from regression_firewall.config.loader import load_config
from regression_firewall.config.schema import ConfigError, parse_config


def write_config(tmp_path, text, name=".regression-firewall.yml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_when_no_file(tmp_path):
    cfg, warnings, path = load_config(tmp_path)
    assert path is None
    assert cfg.thresholds.block_score == 70
    assert cfg.thresholds.review_score == 30
    assert cfg.thresholds.block_on_high is True
    assert cfg.http.enabled and cfg.cli.enabled and cfg.public_api.enabled
    assert any("no probes" in w or "init" in w for w in warnings)


def test_valid_yaml(tmp_path):
    write_config(tmp_path, """
version: 1
surfaces:
  http:
    enabled: true
    base_url: "http://127.0.0.1:8000"
    probes:
      - id: "POST /login"
        method: POST
        path: /login
        body: {"user": "a"}
  cli:
    enabled: false
  public_api:
    probes:
      - id: mypkg
        module: mypkg
severity_overrides:
  header_changed: medium
""")
    cfg, warnings, path = load_config(tmp_path)
    assert path is not None
    assert not warnings
    assert len(cfg.http.probes) == 1
    assert cfg.http.probes[0].method == "POST"
    assert cfg.http.probes[0].id == "POST /login"
    assert cfg.cli.enabled is False
    assert cfg.public_api.probes[0].module == "mypkg"
    assert cfg.severity_overrides == {"header_changed": "medium"}


def test_probe_id_defaults_to_method_path(tmp_path):
    write_config(tmp_path, """
surfaces:
  http:
    base_url: "http://x:1"
    probes:
      - method: GET
        path: /users
""")
    cfg, _, _ = load_config(tmp_path)
    assert cfg.http.probes[0].id == "GET /users"


def test_unknown_top_level_key_rejected(tmp_path):
    write_config(tmp_path, "nope: true\n")
    with pytest.raises(ConfigError, match="unknown top-level keys"):
        load_config(tmp_path)


def test_unknown_surface_rejected(tmp_path):
    write_config(tmp_path, "surfaces:\n  database: true\n")
    with pytest.raises(ConfigError, match="unknown surfaces"):
        load_config(tmp_path)


def test_unknown_probe_key_rejected(tmp_path):
    write_config(tmp_path, """
surfaces:
  cli:
    probes:
      - id: x
        command: ["python", "x.py"]
        magic: true
""")
    with pytest.raises(ConfigError, match="unknown keys"):
        load_config(tmp_path)


def test_invalid_method_rejected(tmp_path):
    write_config(tmp_path, """
surfaces:
  http:
    base_url: "http://x:1"
    probes:
      - method: TRACE
        path: /
""")
    with pytest.raises(ConfigError, match="method"):
        load_config(tmp_path)


def test_http_probe_requires_base_url(tmp_path):
    write_config(tmp_path, """
surfaces:
  http:
    probes:
      - method: GET
        path: /
""")
    with pytest.raises(ConfigError, match="base_url"):
        load_config(tmp_path)


def test_port_template_requires_server_command(tmp_path):
    write_config(tmp_path, """
surfaces:
  http:
    base_url: "http://127.0.0.1:{port}"
    probes:
      - method: GET
        path: /
""")
    with pytest.raises(ConfigError, match=r"\{port\}"):
        load_config(tmp_path)


def test_port_template_ok_with_server(tmp_path):
    write_config(tmp_path, """
surfaces:
  http:
    base_url: "http://127.0.0.1:{port}"
    server:
      command: ["python", "server.py"]
    probes:
      - method: GET
        path: /
""")
    cfg, _, _ = load_config(tmp_path)
    assert cfg.http.server.command == ["python", "server.py"]


def test_thresholds_ordering_validated(tmp_path):
    write_config(tmp_path, "thresholds:\n  review_score: 80\n  block_score: 70\n")
    with pytest.raises(ConfigError, match="review_score"):
        load_config(tmp_path)


def test_invalid_override_severity(tmp_path):
    write_config(tmp_path, "severity_overrides:\n  header_changed: banana\n")
    with pytest.raises(ConfigError, match="banana"):
        load_config(tmp_path)


def test_wrong_type_rejected(tmp_path):
    write_config(tmp_path, "thresholds:\n  review_score: high\n")
    with pytest.raises(ConfigError, match="review_score"):
        load_config(tmp_path)


def test_json_config_supported(tmp_path):
    write_config(tmp_path, '{"version": 1, "thresholds": {"block_score": 90}}',
                 name=".regression-firewall.json")
    cfg, _, _ = load_config(tmp_path)
    assert cfg.thresholds.block_score == 90


def test_explicit_config_path(tmp_path):
    path = write_config(tmp_path, "thresholds:\n  review_score: 10\n", name="custom.yml")
    cfg, _, loaded = load_config(tmp_path, config_path=path)
    assert cfg.thresholds.review_score == 10
    assert loaded == path


def test_probe_body_roundtrip(tmp_path):
    """Regression: probe bodies were once silently dropped during parsing
    (a bad isinstance guard), which made all body-dependent probes useless."""
    write_config(tmp_path, """
surfaces:
  http:
    base_url: "http://127.0.0.1:8000"
    probes:
      - id: "POST /login"
        method: POST
        path: /login
        body: {"username": "alice", "password": "wrong"}
""")
    cfg, _, _ = load_config(tmp_path)
    assert cfg.http.probes[0].body == {"username": "alice", "password": "wrong"}


def test_probe_body_string_and_none(tmp_path):
    write_config(tmp_path, """
surfaces:
  http:
    base_url: "http://127.0.0.1:8000"
    probes:
      - id: post-text
        method: POST
        path: /text
        body: "raw text body"
      - id: no-body
        method: GET
        path: /users
""")
    cfg, _, _ = load_config(tmp_path)
    assert cfg.http.probes[0].body == "raw text body"
    assert cfg.http.probes[1].body is None


def test_undotted_config_filename_accepted(tmp_path):
    """Regression: example configs named without the leading dot were not
    discovered; both spellings must work."""
    write_config(tmp_path, "thresholds:\n  review_score: 12\n", name="regression-firewall.yml")
    cfg, _, path = load_config(tmp_path)
    assert cfg.thresholds.review_score == 12
    assert path.name == "regression-firewall.yml"


def test_invalid_yaml(tmp_path):
    write_config(tmp_path, "a: [::\n")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(tmp_path)


def test_parse_config_rejects_non_mapping():
    with pytest.raises(ConfigError, match="mapping"):
        parse_config([1, 2])
