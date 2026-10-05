from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from .schema import Config, ConfigError, parse_config

CONFIG_FILENAMES = (
    ".regression-firewall.yml",
    ".regression-firewall.yaml",
    ".regression-firewall.json",
    # dotted-less variants are also accepted (easier to spot in file browsers)
    "regression-firewall.yml",
    "regression-firewall.yaml",
    "regression-firewall.json",
)


def find_config_file(project_root: Path) -> Path | None:
    for name in CONFIG_FILENAMES:
        candidate = project_root / name
        if candidate.is_file():
            return candidate
    return None


def load_config(project_root: Path, config_path: Path | None = None) -> tuple:
    """Load and validate configuration.

    Returns ``(Config, warnings, config_file_path)``. A missing config file is
    not an error: defaults apply and a warning is produced.
    """
    path = config_path if config_path is not None else find_config_file(project_root)
    if path is None:
        return Config(), ["No .regression-firewall.yml found; using defaults with no probes. "
                          "Run 'regression-firewall init' to scaffold one."], None
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        import json

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise ConfigError(f"{path}: invalid JSON: {e}") from e
    else:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: invalid YAML: {e}") from e
    cfg = parse_config(raw if raw is not None else {}, source=str(path))
    return cfg, [], path


def config_hash(cfg: Config) -> str:
    payload = json.dumps(cfg.canonical_dict(), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
