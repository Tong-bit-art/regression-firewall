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


# -- custom normalization rules -------------------------------------------------


def test_custom_rule_parses():
    raw = {
        "normalization": {
            "custom_rules": [
                {
                    "name": "order_ref",
                    "pattern": r"^[A-Z]{3}-\d{6}$",
                    "key_hints": ["ref", "order"],
                    "placeholder": "<ORDER_REF>",
                }
            ]
        }
    }
    cfg = parse_config(raw)
    rules = cfg.normalization.custom_rules
    assert len(rules) == 1
    assert rules[0].name == "order_ref"
    assert rules[0].pattern == r"^[A-Z]{3}-\d{6}$"
    assert rules[0].key_hints == ["ref", "order"]
    assert rules[0].placeholder == "<ORDER_REF>"


def test_custom_rule_defaults():
    cfg = parse_config({"normalization": {"custom_rules": [
        {"name": "span_id", "pattern": "[0-9a-f]{16}"},
    ]}})
    rule = cfg.normalization.custom_rules[0]
    assert rule.key_hints == []
    assert rule.placeholder is None
    assert rule.resolved_placeholder() == "<SPAN_ID>"


def test_custom_rule_in_config_hash():
    from regression_firewall.config.loader import config_hash

    with_rules = parse_config({"normalization": {"custom_rules": [
        {"name": "a", "pattern": "x"},
    ]}})
    without = parse_config({})
    assert config_hash(with_rules) != config_hash(without)
    # same config → same hash (custom_rules preserve order)
    assert config_hash(with_rules) == config_hash(parse_config({
        "normalization": {"custom_rules": [{"name": "a", "pattern": "x"}]}
    }))


def test_custom_rule_reject_bad_name():
    with pytest.raises(ConfigError, match=r"custom_rules\[0\].name"):
        parse_config({"normalization": {"custom_rules": [{"name": "Bad Name", "pattern": "x"}]}})


def test_custom_rule_reject_duplicate_name():
    with pytest.raises(ConfigError, match="duplicate rule name"):
        parse_config({"normalization": {"custom_rules": [
            {"name": "a", "pattern": "x"},
            {"name": "a", "pattern": "y"},
        ]}})


def test_custom_rule_reject_bad_pattern():
    with pytest.raises(ConfigError, match="does not compile"):
        parse_config({"normalization": {"custom_rules": [
            {"name": "a", "pattern": "("},
        ]}})


def test_custom_rule_reject_bad_placeholder():
    with pytest.raises(ConfigError, match="placeholder"):
        parse_config({"normalization": {"custom_rules": [
            {"name": "a", "pattern": "x", "placeholder": "TOKEN"},
        ]}})


def test_custom_rule_reject_empty_pattern():
    with pytest.raises(ConfigError, match="pattern"):
        parse_config({"normalization": {"custom_rules": [{"name": "a", "pattern": ""}]}})


def test_custom_rule_reject_bad_key_hints():
    with pytest.raises(ConfigError, match="key_hints"):
        parse_config({"normalization": {"custom_rules": [
            {"name": "a", "pattern": "x", "key_hints": ["ok", ""]},
        ]}})


def test_custom_rule_reject_non_list():
    with pytest.raises(ConfigError, match="must be a list"):
        parse_config({"normalization": {"custom_rules": {"name": "a"}}})


def test_custom_rule_reject_unknown_keys():
    with pytest.raises(ConfigError, match="unknown keys"):
        parse_config({"normalization": {"custom_rules": [
            {"name": "a", "pattern": "x", "regex": "y"},
        ]}})


# -- CLI directory watches -------------------------------------------------------


def _cli_probe_raw(dirs):
    return {"surfaces": {"cli": {"probes": [
        {"id": "gen", "command": ["python", "build.py"], "dirs": dirs},
    ]}}}


def test_cli_dirs_string_and_mapping_forms():
    cfg = parse_config(_cli_probe_raw([
        "out",
        {"path": "dist", "ignore": ["*.map"], "max_files": 100},
    ]))
    dirs = cfg.cli.probes[0].dirs
    assert dirs[0].path == "out"
    assert dirs[0].ignore == []
    assert dirs[0].max_files == 2000
    assert dirs[1].path == "dist"
    assert dirs[1].ignore == ["*.map"]
    assert dirs[1].max_files == 100


def test_cli_dirs_reject_non_list():
    with pytest.raises(ConfigError, match="dirs"):
        parse_config(_cli_probe_raw({"path": "out"}))


def test_cli_dirs_reject_missing_path():
    with pytest.raises(ConfigError, match="path is required"):
        parse_config(_cli_probe_raw([{"ignore": ["a"]}]))


def test_cli_dirs_reject_bad_max_files():
    with pytest.raises(ConfigError, match="max_files"):
        parse_config(_cli_probe_raw([{"path": "out", "max_files": 0}]))


def test_cli_dirs_reject_bad_ignore():
    with pytest.raises(ConfigError, match="ignore"):
        parse_config(_cli_probe_raw([{"path": "out", "ignore": [1]}]))


def test_cli_dirs_reject_unknown_keys():
    with pytest.raises(ConfigError, match="unknown keys"):
        parse_config(_cli_probe_raw([{"path": "out", "deep": True}]))


# -- js_api surface + CLI trace --------------------------------------------------


def test_js_api_surface_parses():
    cfg = parse_config({"surfaces": {"js_api": {"probes": [
        {"id": "entry", "file": "src/index.ts"},
        {"file": "lib/main.js"},
    ]}}})
    assert cfg.js_api.enabled is True
    assert cfg.js_api.probes[0].id == "entry"
    assert cfg.js_api.probes[1].id == "lib/main.js"  # id defaults to file
    assert cfg.js_api.probes[1].file == "lib/main.js"


def test_js_api_surface_enabled_by_default():
    cfg = parse_config({})
    assert cfg.js_api.enabled is True
    assert cfg.js_api.probes == []
    assert "js_api" in cfg.enabled_surfaces()


def test_js_api_probe_requires_file():
    with pytest.raises(ConfigError, match="file is required"):
        parse_config({"surfaces": {"js_api": {"probes": [{"id": "x"}]}}})


def test_js_api_probe_rejects_unknown_keys():
    with pytest.raises(ConfigError, match="unknown keys"):
        parse_config({"surfaces": {"js_api": {"probes": [{"file": "a.js", "module": "x"}]}}})


def test_trace_parses_bool_and_mapping():
    probe_raw = lambda trace: {"surfaces": {"cli": {"probes": [
        {"id": "j", "command": ["python", "j.py"], "trace": trace},
    ]}}}
    cfg = parse_config(probe_raw(True))
    assert cfg.cli.probes[0].trace.fs_writes is True
    assert cfg.cli.probes[0].trace.env_reads is True
    cfg = parse_config(probe_raw({"fs_writes": True}))
    assert cfg.cli.probes[0].trace.fs_writes is True
    assert cfg.cli.probes[0].trace.env_reads is False
    # both false → no trace section at all
    assert parse_config(probe_raw({"fs_writes": False})).cli.probes[0].trace is None
    assert parse_config(probe_raw(False)).cli.probes[0].trace is None
    assert parse_config(probe_raw(None)).cli.probes[0].trace is None


def test_trace_rejects_bad_values():
    probe_raw = lambda trace: {"surfaces": {"cli": {"probes": [
        {"id": "j", "command": ["python", "j.py"], "trace": trace},
    ]}}}
    with pytest.raises(ConfigError, match="must be a mapping or a boolean"):
        parse_config(probe_raw("yes"))
    with pytest.raises(ConfigError, match="unknown keys"):
        parse_config(probe_raw({"reads": True}))
    with pytest.raises(ConfigError, match="must be a boolean"):
        parse_config(probe_raw({"fs_writes": "yes"}))


def test_trace_in_config_hash():
    from regression_firewall.config.loader import config_hash

    with_trace = parse_config({"surfaces": {"cli": {"probes": [
        {"id": "j", "command": ["python", "j.py"], "trace": {"fs_writes": True}},
    ]}}})
    without = parse_config({"surfaces": {"cli": {"probes": [
        {"id": "j", "command": ["python", "j.py"]},
    ]}}})
    assert config_hash(with_trace) != config_hash(without)


def test_trace_sqlite_flag_parses():
    probe_raw = {"surfaces": {"cli": {"probes": [
        {"id": "j", "command": ["python", "j.py"], "trace": {"sqlite": True}},
    ]}}}
    cfg = parse_config(probe_raw)
    assert cfg.cli.probes[0].trace.sqlite is True
    assert cfg.cli.probes[0].trace.fs_writes is False
    # sqlite-only trace survives the all-false -> None collapse
    assert cfg.cli.probes[0].trace is not None


def test_performance_config_parses_and_validates():
    probe_raw = lambda perf: {"surfaces": {"cli": {"probes": [
        {"id": "j", "command": ["python", "j.py"], "performance": perf},
    ]}}}
    cfg = parse_config(probe_raw(True))
    perf = cfg.cli.probes[0].performance
    assert perf.enabled and perf.repeat == 5 and perf.warmup == 1 and perf.max_ratio == 2.0
    cfg = parse_config(probe_raw({"enabled": True, "repeat": 9, "max_ratio": 1.5}))
    perf = cfg.cli.probes[0].performance
    assert perf.repeat == 9 and perf.max_ratio == 1.5
    # disabled -> None (section collapses)
    assert parse_config(probe_raw({"enabled": False})).cli.probes[0].performance is None
    assert parse_config(probe_raw(False)).cli.probes[0].performance is None
    with pytest.raises(ConfigError, match="repeat must be >= 1"):
        parse_config(probe_raw({"repeat": 0}))
    with pytest.raises(ConfigError, match="max_ratio must be > 1.0"):
        parse_config(probe_raw({"max_ratio": 1.0}))
    with pytest.raises(ConfigError, match="unknown keys"):
        parse_config(probe_raw({"budget": 2}))
