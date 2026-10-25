"""OpenAPI 3.x import: derive HTTP probes from an OpenAPI document.

Probes are generated deterministically (document order, first-example
preference) so the same document always yields the same probe suite — and
therefore the same config hash. The document is read at config load time;
explicit probes always win on id conflicts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .schema import PROBE_METHODS, ConfigError, HttpProbeConfig

PATH_PARAM_RE = re.compile(r"\{([^{}]+)\}")
MAX_SCHEMA_DEPTH = 6


def load_openapi_document(path: Path, source: str = "<openapi>") -> dict:
    """Load an OpenAPI document as a dict (JSON or YAML, by suffix — YAML
    parser accepts JSON too, so unknown suffixes fall back to YAML)."""
    if not path.is_file():
        raise ConfigError(f"{source}: OpenAPI file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{source}: invalid JSON in {path.name}: {exc}") from exc
    else:
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ConfigError(f"{source}: invalid YAML in {path.name}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ConfigError(f"{source}: OpenAPI document must be a mapping")
    return doc


def probes_from_openapi(doc: dict, set_values: dict | None = None,
                        methods: list | None = None,
                        source: str = "<openapi>") -> tuple:
    """Generate HttpProbeConfig entries from an OpenAPI 3.x document.

    Returns (probes, warnings). Warnings note defaulted path parameters and
    skipped collisions; they never block capture.
    """
    warnings: list = []
    set_values = dict(set_values or {})
    filter_set = {m.upper() for m in (methods or [])}

    version = str(doc.get("openapi") or "")
    if not version.startswith("3."):
        if doc.get("swagger"):
            raise ConfigError(
                f"{source}: Swagger 2.x documents are not supported; convert to OpenAPI 3.x"
            )
        raise ConfigError(f"{source}: not an OpenAPI 3.x document (missing 'openapi: 3.x')")

    paths = doc.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ConfigError(f"{source}: OpenAPI document defines no 'paths'")

    defaulted_params: list = []
    probes: list = []
    seen_ids: set = set()
    for path_template, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in PROBE_METHODS:
            op = path_item.get(method.lower())
            if not isinstance(op, dict):
                continue
            if filter_set and method not in filter_set:
                continue
            concrete = _concrete_path(str(path_template), set_values, defaulted_params)
            probe_id = f"{method} {concrete}"
            if probe_id in seen_ids:
                warnings.append(
                    f"{source}: probe {probe_id!r} generated more than once "
                    f"(parameterized paths collapse to the same value); keeping the first"
                )
                continue
            seen_ids.add(probe_id)
            probes.append(HttpProbeConfig(
                id=probe_id,
                method=method,
                path=concrete,
                body=_request_body(op, source),
            ))

    if not probes:
        raise ConfigError(
            f"{source}: no HTTP operations found in the OpenAPI document"
            + (f" (methods filter: {', '.join(sorted(filter_set))})" if filter_set else "")
        )

    for name in sorted(set(defaulted_params)):
        if name not in set_values:
            warnings.append(
                f"{source}: path parameter {{{name}}} has no --set value; "
                "defaulted to '1' — set a real value for endpoints that validate inputs"
            )
    return probes, warnings


def merge_openapi_probes(http_cfg, base_dir: Path) -> list:
    """Resolve the configured `openapi:` section against base_dir and append
    generated probes to http_cfg.probes. Explicit probes win on id conflicts.
    Returns warnings."""
    file_value = http_cfg.openapi.file
    doc_path = Path(file_value)
    if not doc_path.is_absolute():
        doc_path = base_dir / doc_path
    source = f"surfaces.http.openapi ({file_value})"
    doc = load_openapi_document(doc_path, source=source)
    probes, warnings = probes_from_openapi(
        doc,
        set_values=http_cfg.openapi.set or {},
        methods=http_cfg.openapi.methods or None,
        source=source,
    )
    explicit_ids = {p.id for p in http_cfg.probes}
    for probe in probes:
        if probe.id in explicit_ids:
            warnings.append(
                f"{source}: explicit probe {probe.id!r} already exists; "
                "the generated one is skipped (explicit probes win)"
            )
            continue
        explicit_ids.add(probe.id)
        http_cfg.probes.append(probe)
    return warnings


def _concrete_path(path_template: str, set_values: dict, defaulted: list) -> str:
    def replace(match):
        name = match.group(1)
        if name in set_values:
            return str(set_values[name])
        defaulted.append(name)
        return "1"

    return PATH_PARAM_RE.sub(replace, path_template)


def _request_body(operation: dict, source: str):
    """Best-effort deterministic body from requestBody: explicit example,
    then the first named example, then a schema-derived skeleton. None when
    no JSON media type is declared."""
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    content = request_body.get("content") or {}
    media = content.get("application/json")
    if not isinstance(media, dict):
        return None
    if "example" in media:
        return media["example"]
    for example in (media.get("examples") or {}).values():
        if isinstance(example, dict) and "value" in example:
            return example["value"]
    schema = media.get("schema")
    if isinstance(schema, dict):
        return _schema_example(schema)
    return None


def _schema_example(schema: dict, depth: int = 0):
    """A deterministic minimal example for a JSON schema: example > default >
    first enum value > type-based skeleton."""
    if not isinstance(schema, dict) or depth > MAX_SCHEMA_DEPTH:
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    schema_type = schema.get("type")
    if isinstance(schema_type, list):  # OpenAPI 3.1 type unions
        schema_type = next((t for t in schema_type if t != "null"), None)
    if schema_type == "object" or "properties" in schema:
        return {
            name: _schema_example(sub, depth + 1)
            for name, sub in (schema.get("properties") or {}).items()
        }
    if schema_type == "array":
        items = schema.get("items")
        return [_schema_example(items, depth + 1)] if isinstance(items, dict) else []
    if schema_type == "string":
        return ""
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "boolean":
        return False
    return None
