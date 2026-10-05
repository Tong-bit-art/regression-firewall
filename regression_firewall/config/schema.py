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
class HttpSurfaceConfig:
    enabled: bool = True
    base_url: str = ""
    server: Optional[ServerConfig] = None
    ready_path: str = "/"
    ready_timeout: float = 30.0
    discover_app: Optional[str] = None
    probes: list = field(default_factory=list)  # list[HttpProbeConfig]


@dataclass
class CliProbeConfig:
    id: str = ""
    command: list = field(default_factory=list)
    cwd: str = "."
    env: dict = field(default_factory=dict)
    files: list = field(default_factory=list)
    timeout: float = 60.0


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
        return out

    def canonical_dict(self) -> dict:
        """Config content as a plain dict; used for the config hash."""
        return {
            "version": self.version,
            "surfaces": {
                "http": _strip_none(dataclasses.asdict(self.http)),
                "cli": _strip_none(dataclasses.asdict(self.cli)),
                "public_api": _strip_none(dataclasses.asdict(self.public_api)),
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
    known_surfaces = {"http", "cli", "public_api"}
    unknown_surfaces = sorted(set(surfaces) - known_surfaces)
    if unknown_surfaces:
        raise ConfigError(
            f"{source}: unknown surfaces: {', '.join(unknown_surfaces)}. "
            f"Supported: {', '.join(sorted(known_surfaces))}"
        )
    cfg.http = _parse_http(surfaces.get("http"), source)
    cfg.cli = _parse_cli(surfaces.get("cli"), source)
    cfg.public_api = _parse_api(surfaces.get("public_api"), source)

    cfg.ignore = _parse_section(
        raw.get("ignore"), IgnoreConfig, {"headers": "list", "json_paths": "list"}, "ignore", source
    )
    cfg.normalization = _parse_section(
        raw.get("normalization"),
        NormalizationConfig,
        {f.name: "bool" for f in dataclasses.fields(NormalizationConfig)},
        "normalization",
        source,
    )
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


def _parse_http(raw, source: str) -> HttpSurfaceConfig:
    cfg = HttpSurfaceConfig()
    if raw is None:
        return cfg
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: surfaces.http must be a mapping")
    known = {"enabled", "base_url", "server", "ready_path", "ready_timeout", "discover_app", "probes"}
    _check_keys(raw, known, "surfaces.http", source)
    cfg.enabled = _as_bool(raw.get("enabled", True), "surfaces.http.enabled", source)
    cfg.base_url = _as_str(raw.get("base_url", ""), "surfaces.http.base_url", source)
    cfg.ready_path = _as_str(raw.get("ready_path", "/"), "surfaces.http.ready_path", source)
    cfg.ready_timeout = _as_number(raw.get("ready_timeout", 30.0), "surfaces.http.ready_timeout", source)
    cfg.discover_app = _as_optional_str(raw.get("discover_app"), "surfaces.http.discover_app", source)
    server_raw = raw.get("server")
    if server_raw is not None:
        if not isinstance(server_raw, dict):
            raise ConfigError(f"{source}: surfaces.http.server must be a mapping")
        _check_keys(server_raw, {"command"}, "surfaces.http.server", source)
        cfg.server = ServerConfig(command=_as_str_list(server_raw.get("command", []), "surfaces.http.server.command", source))
        if not cfg.server.command:
            raise ConfigError(f"{source}: surfaces.http.server.command must be a non-empty list")
    probes_raw = raw.get("probes") or []
    if not isinstance(probes_raw, list):
        raise ConfigError(f"{source}: surfaces.http.probes must be a list")
    for i, probe_raw in enumerate(probes_raw):
        cfg.probes.append(_parse_http_probe(probe_raw, i, source))
    return cfg


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
        known_probe = {"id", "command", "cwd", "env", "files", "timeout"}
        _check_keys(probe_raw, known_probe, f"surfaces.cli.probes[{i}]", source)
        command = _as_str_list(probe_raw.get("command", []), f"surfaces.cli.probes[{i}].command", source)
        probe = CliProbeConfig(
            id=_as_str(probe_raw.get("id") or " ".join(command), f"surfaces.cli.probes[{i}].id", source),
            command=command,
            cwd=_as_str(probe_raw.get("cwd", "."), f"surfaces.cli.probes[{i}].cwd", source),
            env=_as_str_map(probe_raw.get("env") or {}, f"surfaces.cli.probes[{i}].env", source),
            files=_as_str_list(probe_raw.get("files") or [], f"surfaces.cli.probes[{i}].files", source),
            timeout=_as_number(probe_raw.get("timeout", 60.0), f"surfaces.cli.probes[{i}].timeout", source),
        )
        cfg.probes.append(probe)
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
