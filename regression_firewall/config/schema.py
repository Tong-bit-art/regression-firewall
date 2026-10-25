from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional

from ..models.change import MISSING


class ConfigError(ValueError):
    """Raised when the configuration file is invalid."""


PROBE_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


@dataclass
class ServerConfig:
    command: list = field(default_factory=list)
    cwd: str = "."  # relative to the project root


@dataclass
class HttpProbeConfig:
    id: str = ""
    method: str = "GET"
    path: str = "/"
    headers: dict = field(default_factory=dict)
    body: Any = None
    follow_redirects: bool = True
    timeout: float = 15.0


@dataclass
class OpenApiConfig:
    """Derive HTTP probes from an OpenAPI 3.x document at config load time.

    `file` is resolved relative to the config file's directory. `set` maps
    {path} parameter names to concrete values; unmapped parameters default to
    '1' (with a warning). `methods` optionally filters HTTP methods.
    """

    file: str = ""
    set: dict = field(default_factory=dict)
    methods: list = field(default_factory=list)


@dataclass
class HttpSurfaceConfig:
    enabled: bool = True
    base_url: str = ""
    server: Optional[ServerConfig] = None
    ready_path: str = "/"
    ready_timeout: float = 30.0
    discover_app: Optional[str] = None
    openapi: Optional[OpenApiConfig] = None
    probes: list = field(default_factory=list)  # list[HttpProbeConfig]


@dataclass
class DirWatchConfig:
    """A watched directory for a CLI probe: every regular file below it is
    tracked (content hash + size), so files the probe creates anywhere in the
    tree are noticed without listing them one by one."""

    path: str = ""
    ignore: list = field(default_factory=list)  # fnmatch globs (dir names or rel posix paths)
    max_files: int = 2000


@dataclass
class CliProbeConfig:
    id: str = ""
    command: list = field(default_factory=list)
    cwd: str = "."
    env: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    dirs: list = field(default_factory=list)  # list[DirWatchConfig]
    trace: Optional["TraceConfig"] = None  # opt-in Python behavior tracing
    performance: Optional["PerformanceConfig"] = None  # opt-in timing
    timeout: float = 60.0


@dataclass
class PerformanceConfig:
    """Opt-in runtime measurement for a CLI probe.

    The probe runs `warmup` untimed times, then `repeat` timed times; the
    captured behavior comes from the last timed run, and the MEDIAN duration
    is recorded. At diff time, median_after / median_before above `max_ratio`
    is a runtime regression. Timing is machine-dependent and noisy: this is
    never on by default, and the verdict it produces is UNCERTAIN (human
    review), never an automatic BLOCK."""

    enabled: bool = False
    repeat: int = 5
    warmup: int = 1
    max_ratio: float = 2.0


@dataclass
class TraceConfig:
    """Opt-in behavior tracing for a CLI probe (Python commands only).

    Tracing works by injecting a sitecustomize.py via PYTHONPATH, so it
    records only Python processes. fs_writes records paths the command
    writes; env_reads records the NAMES of environment variables read
    (never values)."""

    fs_writes: bool = False
    env_reads: bool = False
    sqlite: bool = False  # trace stdlib sqlite3 query shapes + write tables


@dataclass
class JsApiProbeConfig:
    """A static public-API probe for one JavaScript/TypeScript entry file."""

    id: str = ""
    file: str = ""  # project-relative path to the entry file


@dataclass
class JsApiSurfaceConfig:
    enabled: bool = True
    probes: list = field(default_factory=list)  # list[JsApiProbeConfig]


@dataclass
class CliSurfaceConfig:
    enabled: bool = True
    probes: list = field(default_factory=list)  # list[CliProbeConfig]


@dataclass
class ApiProbeConfig:
    id: str = ""
    module: str = ""
    include_private: bool = False


@dataclass
class ApiSurfaceConfig:
    enabled: bool = True
    probes: list = field(default_factory=list)  # list[ApiProbeConfig]


@dataclass
class IgnoreConfig:
    headers: list = field(default_factory=lambda: ["date", "content-length"])
    json_paths: list = field(default_factory=list)


CUSTOM_RULE_NAME_RE_PATTERN = r"^[a-z][a-z0-9_-]*$"


@dataclass
class CustomRuleConfig:
    """A user-defined normalization rule.

    ``pattern`` is applied to string values: full-match for keyed values
    (JSON strings, headers, cookies), and global re.sub for plain text
    (stdout/stderr) — but only when the rule declares no ``key_hints``.
    """

    name: str = ""
    pattern: str = ""
    key_hints: list = field(default_factory=list)
    placeholder: Optional[str] = None

    def resolved_placeholder(self) -> str:
        return self.placeholder if self.placeholder else f"<{self.name.upper()}>"


@dataclass
class NormalizationConfig:
    uuid: bool = True
    iso_datetime: bool = True
    epoch_timestamps: bool = True
    request_ids: bool = True
    tokens: bool = True
    temp_paths: bool = True
    durations: bool = True
    float_precision: bool = True
    whitespace: bool = True
    ansi: bool = True
    custom_rules: list = field(default_factory=list)  # list[CustomRuleConfig]


@dataclass
class ThresholdsConfig:
    review_score: int = 30
    block_score: int = 70
    block_on_high: bool = True


@dataclass
class ReportConfig:
    markdown: bool = True
    json: bool = True


@dataclass
class RedactionConfig:
    """Capture-time secret redaction applied to snapshots (NOT just diffs).

    Snapshots are stored on disk and may be shared in bug reports; secrets
    that reach them through responses must be masked before storage.
    """

    secrets: bool = True


@dataclass
class Config:
    version: int = 1
    http: HttpSurfaceConfig = field(default_factory=HttpSurfaceConfig)
    cli: CliSurfaceConfig = field(default_factory=CliSurfaceConfig)
    public_api: ApiSurfaceConfig = field(default_factory=ApiSurfaceConfig)
    js_api: JsApiSurfaceConfig = field(default_factory=JsApiSurfaceConfig)
    ignore: IgnoreConfig = field(default_factory=IgnoreConfig)
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    redaction: RedactionConfig = field(default_factory=RedactionConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    severity_overrides: dict = field(default_factory=dict)

    def enabled_surfaces(self) -> list:
        out = []
        if self.http.enabled:
            out.append("http")
        if self.cli.enabled:
            out.append("cli")
        if self.public_api.enabled:
            out.append("public_api")
        if self.js_api.enabled:
            out.append("js_api")
        return out

    def canonical_dict(self) -> dict:
        """Config content as a plain dict; used for the config hash."""
        return {
            "version": self.version,
            "surfaces": {
                "http": _strip_none(dataclasses.asdict(self.http)),
                "cli": _strip_none(dataclasses.asdict(self.cli)),
                "public_api": _strip_none(dataclasses.asdict(self.public_api)),
                "js_api": _strip_none(dataclasses.asdict(self.js_api)),
            },
            "ignore": dataclasses.asdict(self.ignore),
            "normalization": dataclasses.asdict(self.normalization),
            "redaction": dataclasses.asdict(self.redaction),
            "thresholds": dataclasses.asdict(self.thresholds),
            "report": dataclasses.asdict(self.report),
            "severity_overrides": self.severity_overrides,
        }


def _strip_none(d: dict) -> dict:
    # Optional sections (like server) must not churn the config hash when unset.
    return {k: v for k, v in d.items() if v is not None}


# ---------------------------------------------------------------------------
# Parsing


def parse_config(raw: dict, source: str = "<config>") -> Config:
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: top-level configuration must be a mapping")

    known = {"version", "surfaces", "ignore", "normalization", "redaction", "thresholds",
             "report", "severity_overrides"}
    unknown = sorted(set(raw) - known)
    cfg = Config()
    if unknown:
        raise ConfigError(
            f"{source}: unknown top-level keys: {', '.join(unknown)}. "
            f"Expected keys: {', '.join(sorted(known))}"
        )

    version = raw.get("version", 1)
    if version != 1:
        raise ConfigError(f"{source}: unsupported config version {version!r} (expected 1)")
    cfg.version = 1

    surfaces = raw.get("surfaces") or {}
    if not isinstance(surfaces, dict):
        raise ConfigError(f"{source}: 'surfaces' must be a mapping")
    known_surfaces = {"http", "cli", "public_api", "js_api"}
    unknown_surfaces = sorted(set(surfaces) - known_surfaces)
    if unknown_surfaces:
        raise ConfigError(
            f"{source}: unknown surfaces: {', '.join(unknown_surfaces)}. "
            f"Supported: {', '.join(sorted(known_surfaces))}"
        )
    cfg.http = _parse_http(surfaces.get("http"), source)
    cfg.cli = _parse_cli(surfaces.get("cli"), source)
    cfg.public_api = _parse_api(surfaces.get("public_api"), source)
    cfg.js_api = _parse_js_api(surfaces.get("js_api"), source)

    cfg.ignore = _parse_section(
        raw.get("ignore"), IgnoreConfig, {"headers": "list", "json_paths": "list"}, "ignore", source
    )
    cfg.normalization = _parse_normalization(raw.get("normalization"), source)
    cfg.redaction = _parse_section(
        raw.get("redaction"),
        RedactionConfig,
        {f.name: "bool" for f in dataclasses.fields(RedactionConfig)},
        "redaction",
        source,
    )
    cfg.thresholds = _parse_section(
        raw.get("thresholds"),
        ThresholdsConfig,
        {"review_score": "int", "block_score": "int", "block_on_high": "bool"},
        "thresholds",
        source,
    )
    cfg.report = _parse_section(
        raw.get("report"), ReportConfig, {"markdown": "bool", "json": "bool"}, "report", source
    )

    overrides = raw.get("severity_overrides") or {}
    if not isinstance(overrides, dict):
        raise ConfigError(f"{source}: 'severity_overrides' must be a mapping")
    from ..scoring.severity import SEVERITIES

    for key, value in overrides.items():
        if value not in SEVERITIES:
            raise ConfigError(
                f"{source}: severity_overrides[{key!r}] = {value!r} is not one of "
                f"{', '.join(SEVERITIES)}"
            )
    cfg.severity_overrides = dict(overrides)

    _validate(cfg, source)
    return cfg


def _validate(cfg: Config, source: str) -> None:
    if cfg.thresholds.review_score >= cfg.thresholds.block_score:
        raise ConfigError(
            f"{source}: thresholds.review_score ({cfg.thresholds.review_score}) must be "
            f"lower than thresholds.block_score ({cfg.thresholds.block_score})"
        )
    http = cfg.http
    if http.enabled and http.probes:
        if not http.base_url:
            raise ConfigError(f"{source}: surfaces.http.base_url is required when HTTP probes are defined")
        if "{port}" in http.base_url and not (http.server and http.server.command):
            raise ConfigError(
                f"{source}: base_url contains {{port}} but surfaces.http.server.command is not set; "
                "the tool needs to manage the server to know the port"
            )
    for probe in cfg.http.probes:
        if probe.method not in PROBE_METHODS:
            raise ConfigError(
                f"{source}: HTTP probe {probe.id!r}: method must be one of {', '.join(PROBE_METHODS)}"
            )
        if not probe.path.startswith("/"):
            raise ConfigError(f"{source}: HTTP probe {probe.id!r}: path must start with '/'")
    for probe in cfg.cli.probes:
        if not probe.command:
            raise ConfigError(f"{source}: CLI probe {probe.id!r}: command must be a non-empty list")
    for probe in cfg.public_api.probes:
        if not probe.module:
            raise ConfigError(f"{source}: public_api probe {probe.id!r}: module is required")
    for probe in cfg.js_api.probes:
        if not probe.file:
            raise ConfigError(f"{source}: js_api probe {probe.id!r}: file is required")


def _parse_http(raw, source: str) -> HttpSurfaceConfig:
    cfg = HttpSurfaceConfig()
    if raw is None:
        return cfg
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: surfaces.http must be a mapping")
    known = {"enabled", "base_url", "server", "ready_path", "ready_timeout", "discover_app",
             "openapi", "probes"}
    _check_keys(raw, known, "surfaces.http", source)
    cfg.enabled = _as_bool(raw.get("enabled", True), "surfaces.http.enabled", source)
    cfg.base_url = _as_str(raw.get("base_url", ""), "surfaces.http.base_url", source)
    cfg.ready_path = _as_str(raw.get("ready_path", "/"), "surfaces.http.ready_path", source)
    cfg.ready_timeout = _as_number(raw.get("ready_timeout", 30.0), "surfaces.http.ready_timeout", source)
    cfg.discover_app = _as_optional_str(raw.get("discover_app"), "surfaces.http.discover_app", source)
    cfg.openapi = _parse_openapi(raw.get("openapi"), source)
    server_raw = raw.get("server")
    if server_raw is not None:
        if not isinstance(server_raw, dict):
            raise ConfigError(f"{source}: surfaces.http.server must be a mapping")
        _check_keys(server_raw, {"command", "cwd"}, "surfaces.http.server", source)
        cfg.server = ServerConfig(
            command=_as_str_list(server_raw.get("command", []), "surfaces.http.server.command", source),
            cwd=_as_str(server_raw.get("cwd", "."), "surfaces.http.server.cwd", source),
        )
        if not cfg.server.command:
            raise ConfigError(f"{source}: surfaces.http.server.command must be a non-empty list")
    probes_raw = raw.get("probes") or []
    if not isinstance(probes_raw, list):
        raise ConfigError(f"{source}: surfaces.http.probes must be a list")
    for i, probe_raw in enumerate(probes_raw):
        cfg.probes.append(_parse_http_probe(probe_raw, i, source))
    return cfg


def _parse_openapi(raw, source: str) -> OpenApiConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: surfaces.http.openapi must be a mapping")
    _check_keys(raw, {"file", "set", "methods"}, "surfaces.http.openapi", source)
    file_value = raw.get("file")
    if not isinstance(file_value, str) or not file_value.strip():
        raise ConfigError(f"{source}: surfaces.http.openapi.file is required")
    set_values = raw.get("set") or {}
    if not isinstance(set_values, dict) or not all(
        isinstance(k, str) and isinstance(v, (str, int, float)) for k, v in set_values.items()
    ):
        raise ConfigError(
            f"{source}: surfaces.http.openapi.set must be a mapping of "
            "parameter names to string/number values"
        )
    methods = raw.get("methods") or []
    if not isinstance(methods, list) or not methods:
        methods = []
    else:
        if not all(isinstance(m, str) and m.strip() for m in methods):
            raise ConfigError(
                f"{source}: surfaces.http.openapi.methods must be a list of method names"
            )
        bad = [m for m in methods if m.strip().upper() not in PROBE_METHODS]
        if bad:
            raise ConfigError(
                f"{source}: surfaces.http.openapi.methods contains unsupported "
                f"method(s) {', '.join(bad)}; supported: {', '.join(PROBE_METHODS)}"
            )
    return OpenApiConfig(
        file=file_value,
        set={str(k): v for k, v in set_values.items()},
        methods=[str(m).strip().upper() for m in methods],
    )


def _parse_http_probe(raw, index: int, source: str) -> HttpProbeConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: surfaces.http.probes[{index}] must be a mapping")
    known = {"id", "method", "path", "headers", "body", "follow_redirects", "timeout"}
    _check_keys(raw, known, f"surfaces.http.probes[{index}]", source)
    method = str(raw.get("method", "GET")).upper()
    path = _as_str(raw.get("path", "/"), f"surfaces.http.probes[{index}].path", source)
    probe = HttpProbeConfig(
        method=method,
        path=path,
        id=_as_str(raw.get("id") or f"{method} {path}", f"surfaces.http.probes[{index}].id", source),
        headers=_as_str_map(raw.get("headers") or {}, f"surfaces.http.probes[{index}].headers", source),
        body=raw.get("body"),
        follow_redirects=_as_bool(
            raw.get("follow_redirects", True), f"surfaces.http.probes[{index}].follow_redirects", source
        ),
        timeout=_as_number(raw.get("timeout", 15.0), f"surfaces.http.probes[{index}].timeout", source),
    )
    return probe


def _parse_cli(raw, source: str) -> CliSurfaceConfig:
    cfg = CliSurfaceConfig()
    if raw is None:
        return cfg
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: surfaces.cli must be a mapping")
    known = {"enabled", "probes"}
    _check_keys(raw, known, "surfaces.cli", source)
    cfg.enabled = _as_bool(raw.get("enabled", True), "surfaces.cli.enabled", source)
    probes_raw = raw.get("probes") or []
    if not isinstance(probes_raw, list):
        raise ConfigError(f"{source}: surfaces.cli.probes must be a list")
    for i, probe_raw in enumerate(probes_raw):
        if not isinstance(probe_raw, dict):
            raise ConfigError(f"{source}: surfaces.cli.probes[{i}] must be a mapping")
        known_probe = {"id", "command", "cwd", "env", "files", "dirs", "trace",
                       "performance", "timeout"}
        _check_keys(probe_raw, known_probe, f"surfaces.cli.probes[{i}]", source)
        command = _as_str_list(probe_raw.get("command", []), f"surfaces.cli.probes[{i}].command", source)
        probe = CliProbeConfig(
            id=_as_str(probe_raw.get("id") or " ".join(command), f"surfaces.cli.probes[{i}].id", source),
            command=command,
            cwd=_as_str(probe_raw.get("cwd", "."), f"surfaces.cli.probes[{i}].cwd", source),
            env=_as_str_map(probe_raw.get("env") or {}, f"surfaces.cli.probes[{i}].env", source),
            files=_as_str_list(probe_raw.get("files") or [], f"surfaces.cli.probes[{i}].files", source),
            dirs=_parse_dir_watches(probe_raw.get("dirs"), i, source),
            trace=_parse_trace(probe_raw.get("trace"), i, source),
            performance=_parse_performance(probe_raw.get("performance"), i, source),
            timeout=_as_number(probe_raw.get("timeout", 60.0), f"surfaces.cli.probes[{i}].timeout", source),
        )
        cfg.probes.append(probe)
    return cfg


def _parse_dir_watches(raw, probe_index: int, source: str) -> list:
    where = f"surfaces.cli.probes[{probe_index}].dirs"
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ConfigError(f"{source}: {where} must be a list")
    watches = []
    for i, item in enumerate(raw):
        entry_where = f"{where}[{i}]"
        if isinstance(item, str):
            item = {"path": item}
        if not isinstance(item, dict):
            raise ConfigError(
                f"{source}: {entry_where} must be a mapping or a path string"
            )
        _check_keys(item, {"path", "ignore", "max_files"}, entry_where, source)
        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ConfigError(f"{source}: {entry_where}.path is required")
        ignore = item.get("ignore", [])
        if not isinstance(ignore, list) or not all(isinstance(g, str) and g for g in ignore):
            raise ConfigError(
                f"{source}: {entry_where}.ignore must be a list of non-empty glob strings"
            )
        max_files = item.get("max_files", 2000)
        if isinstance(max_files, bool) or not isinstance(max_files, int) or max_files < 1:
            raise ConfigError(
                f"{source}: {entry_where}.max_files must be a positive integer"
            )
        watches.append(DirWatchConfig(path=path, ignore=list(ignore), max_files=max_files))
    return watches


def _parse_performance(raw, probe_index: int, source: str) -> PerformanceConfig | None:
    if raw is None:
        return None
    where = f"surfaces.cli.probes[{probe_index}].performance"
    if isinstance(raw, bool):
        raw = {"enabled": raw}
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: {where} must be a mapping or a boolean")
    _check_keys(raw, {"enabled", "repeat", "warmup", "max_ratio"}, where, source)
    perf = PerformanceConfig(
        enabled=_as_bool(raw.get("enabled", True), f"{where}.enabled", source),
        repeat=_as_int(raw.get("repeat", 5), f"{where}.repeat", source),
        warmup=_as_int(raw.get("warmup", 1), f"{where}.warmup", source),
        max_ratio=_as_number(raw.get("max_ratio", 2.0), f"{where}.max_ratio", source),
    )
    if not perf.enabled:
        return None
    if perf.repeat < 1:
        raise ConfigError(f"{source}: {where}.repeat must be >= 1")
    if perf.warmup < 0:
        raise ConfigError(f"{source}: {where}.warmup must be >= 0")
    if perf.max_ratio <= 1.0:
        raise ConfigError(f"{source}: {where}.max_ratio must be > 1.0")
    return perf


def _parse_trace(raw, probe_index: int, source: str) -> TraceConfig | None:
    if raw is None:
        return None
    where = f"surfaces.cli.probes[{probe_index}].trace"
    if isinstance(raw, bool):
        raw = {"fs_writes": raw, "env_reads": raw}
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: {where} must be a mapping or a boolean")
    _check_keys(raw, {"fs_writes", "env_reads", "sqlite"}, where, source)
    trace = TraceConfig(
        fs_writes=_as_bool(raw.get("fs_writes", False), f"{where}.fs_writes", source),
        env_reads=_as_bool(raw.get("env_reads", False), f"{where}.env_reads", source),
        sqlite=_as_bool(raw.get("sqlite", False), f"{where}.sqlite", source),
    )
    if not (trace.fs_writes or trace.env_reads or trace.sqlite):
        return None
    return trace


def _parse_js_api(raw, source: str) -> JsApiSurfaceConfig:
    cfg = JsApiSurfaceConfig()
    if raw is None:
        return cfg
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: surfaces.js_api must be a mapping")
    known = {"enabled", "probes"}
    _check_keys(raw, known, "surfaces.js_api", source)
    cfg.enabled = _as_bool(raw.get("enabled", True), "surfaces.js_api.enabled", source)
    probes_raw = raw.get("probes") or []
    if not isinstance(probes_raw, list):
        raise ConfigError(f"{source}: surfaces.js_api.probes must be a list")
    for i, probe_raw in enumerate(probes_raw):
        if not isinstance(probe_raw, dict):
            raise ConfigError(f"{source}: surfaces.js_api.probes[{i}] must be a mapping")
        known_probe = {"id", "file"}
        _check_keys(probe_raw, known_probe, f"surfaces.js_api.probes[{i}]", source)
        file_value = probe_raw.get("file", "")
        cfg.probes.append(
            JsApiProbeConfig(
                id=_as_str(probe_raw.get("id") or file_value,
                           f"surfaces.js_api.probes[{i}].id", source),
                file=_as_str(file_value, f"surfaces.js_api.probes[{i}].file", source),
            )
        )
    return cfg


def _parse_api(raw, source: str) -> ApiSurfaceConfig:
    cfg = ApiSurfaceConfig()
    if raw is None:
        return cfg
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: surfaces.public_api must be a mapping")
    known = {"enabled", "probes"}
    _check_keys(raw, known, "surfaces.public_api", source)
    cfg.enabled = _as_bool(raw.get("enabled", True), "surfaces.public_api.enabled", source)
    probes_raw = raw.get("probes") or []
    if not isinstance(probes_raw, list):
        raise ConfigError(f"{source}: surfaces.public_api.probes must be a list")
    for i, probe_raw in enumerate(probes_raw):
        if not isinstance(probe_raw, dict):
            raise ConfigError(f"{source}: surfaces.public_api.probes[{i}] must be a mapping")
        known_probe = {"id", "module", "include_private"}
        _check_keys(probe_raw, known_probe, f"surfaces.public_api.probes[{i}]", source)
        module = _as_str(probe_raw.get("module", ""), f"surfaces.public_api.probes[{i}].module", source)
        cfg.probes.append(
            ApiProbeConfig(
                id=_as_str(probe_raw.get("id") or module, f"surfaces.public_api.probes[{i}].id", source),
                module=module,
                include_private=_as_bool(
                    probe_raw.get("include_private", False),
                    f"surfaces.public_api.probes[{i}].include_private",
                    source,
                ),
            )
        )
    return cfg


def _parse_section(raw, dataclass_cls, type_map, name: str, source: str):
    cfg = dataclass_cls()
    if raw is None:
        return cfg
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: '{name}' must be a mapping")
    _check_keys(raw, set(type_map), name, source)
    for key, kind in type_map.items():
        if key in raw:
            value = raw[key]
            if kind == "bool":
                setattr(cfg, key, _as_bool(value, f"{name}.{key}", source))
            elif kind == "int":
                setattr(cfg, key, _as_int(value, f"{name}.{key}", source))
            else:
                setattr(cfg, key, _as_str_list(value, f"{name}.{key}", source))
    return cfg


NORMALIZATION_BOOL_KEYS = (
    "uuid", "iso_datetime", "epoch_timestamps", "request_ids", "tokens",
    "temp_paths", "durations", "float_precision", "whitespace", "ansi",
)


def _parse_normalization(raw, source: str) -> NormalizationConfig:
    cfg = NormalizationConfig()
    if raw is None:
        return cfg
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: 'normalization' must be a mapping")
    _check_keys(raw, set(NORMALIZATION_BOOL_KEYS) | {"custom_rules"}, "normalization", source)
    for key in NORMALIZATION_BOOL_KEYS:
        if key in raw:
            setattr(cfg, key, _as_bool(raw[key], f"normalization.{key}", source))
    if "custom_rules" in raw:
        cfg.custom_rules = _parse_custom_rules(raw["custom_rules"], source)
    return cfg


def _parse_custom_rules(raw, source: str) -> list:
    import re as _re

    if not isinstance(raw, list):
        raise ConfigError(f"{source}: normalization.custom_rules must be a list")
    rules = []
    seen_names = set()
    for i, item in enumerate(raw):
        where = f"normalization.custom_rules[{i}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{source}: {where} must be a mapping")
        _check_keys(item, {"name", "pattern", "key_hints", "placeholder"}, where, source)
        name = item.get("name")
        if not isinstance(name, str) or not _re.match(CUSTOM_RULE_NAME_RE_PATTERN, name):
            raise ConfigError(
                f"{source}: {where}.name must match {CUSTOM_RULE_NAME_RE_PATTERN!r}, got {name!r}"
            )
        if name in seen_names:
            raise ConfigError(f"{source}: {where}: duplicate rule name {name!r}")
        seen_names.add(name)
        pattern = item.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ConfigError(f"{source}: {where}.pattern must be a non-empty string")
        try:
            _re.compile(pattern)
        except _re.error as exc:
            raise ConfigError(f"{source}: {where}.pattern does not compile: {exc}") from exc
        key_hints = item.get("key_hints", [])
        if not isinstance(key_hints, list) or not all(
            isinstance(h, str) and h for h in key_hints
        ):
            raise ConfigError(
                f"{source}: {where}.key_hints must be a list of non-empty strings"
            )
        placeholder = item.get("placeholder")
        if placeholder is not None:
            if (
                not isinstance(placeholder, str)
                or len(placeholder) < 3
                or not placeholder.startswith("<")
                or not placeholder.endswith(">")
                or "<" in placeholder[1:-1]
                or ">" in placeholder[1:-1]
            ):
                raise ConfigError(
                    f"{source}: {where}.placeholder must look like '<TOKEN>' "
                    f"(angle-bracketed, no nested brackets), got {placeholder!r}"
                )
        rules.append(
            CustomRuleConfig(
                name=name, pattern=pattern, key_hints=list(key_hints), placeholder=placeholder
            )
        )
    return rules


def _check_keys(raw: dict, known: set, where: str, source: str) -> None:
    unknown = sorted(set(raw) - known)
    if unknown:
        raise ConfigError(
            f"{source}: unknown keys in {where}: {', '.join(unknown)}. "
            f"Expected: {', '.join(sorted(known))}"
        )


def _as_bool(value, where: str, source: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"{source}: {where} must be a boolean, got {value!r}")


def _as_int(value, where: str, source: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{source}: {where} must be an integer, got {value!r}")
    return value


def _as_number(value, where: str, source: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{source}: {where} must be a number, got {value!r}")
    return float(value)


def _as_str(value, where: str, source: str) -> str:
    if isinstance(value, str):
        return value
    raise ConfigError(f"{source}: {where} must be a string, got {value!r}")


def _as_optional_str(value, where: str, source: str):
    if value is None:
        return None
    return _as_str(value, where, source)


def _as_str_list(value, where: str, source: str) -> list:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    raise ConfigError(f"{source}: {where} must be a list of strings, got {value!r}")


def _as_str_map(value, where: str, source: str) -> dict:
    if isinstance(value, dict) and all(
        isinstance(k, str) and (isinstance(v, (str, int, float, bool)) or v is None)
        for k, v in value.items()
    ):
        return {str(k): v for k, v in value.items()}
    raise ConfigError(f"{source}: {where} must be a mapping of string keys to scalar values")
