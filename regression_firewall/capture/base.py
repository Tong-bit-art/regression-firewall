"""Behavior capture: run configured probes and produce raw ProbeCaptures."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .. import SNAPSHOT_SCHEMA_VERSION, __version__
from ..config.loader import config_hash
from ..config.schema import Config
from ..discovery.project import detect_project
from ..models.snapshot import ProbeCapture, Snapshot
from ..provenance import collect_git_state


class CaptureError(RuntimeError):
    """A capture-level failure (probe infrastructure, not subject behavior)."""


def run_capture(config: Config, project_root: Path, artifacts_dir: Path,
                only_probes=None) -> tuple:
    """Run all enabled, configured probes.

    ``only_probes`` (selective mode) maps surface name -> set of probe ids to
    capture; ``None`` captures everything. Probes filtered out by selection
    are NOT run at all. Returns (Snapshot, warnings).
    """
    import dataclasses

    warnings: list = []
    surfaces: dict = {}

    def pick(surface: str, section):
        """Section with only the selected probes, or None when nothing (or
        everything unselected) — the caller's enabled-but-empty warning only
        makes sense outside selective mode."""
        if only_probes is None:
            return section
        kept = [p for p in section.probes if p.id in only_probes.get(surface, set())]
        return dataclasses.replace(section, probes=kept)

    http_section = pick("http", config.http) if config.http.enabled else None
    if http_section is not None:
        if http_section.probes:
            from .http_probe import capture_http_probes

            surfaces["http"], http_warnings = capture_http_probes(
                http_section, project_root, artifacts_dir, config.redaction
            )
            warnings.extend(http_warnings)
        elif only_probes is None:
            warnings.append("surface 'http' is enabled but no probes are configured")

    cli_section = pick("cli", config.cli) if config.cli.enabled else None
    if cli_section is not None:
        if cli_section.probes:
            from .cli import capture_cli_probes

            surfaces["cli"], cli_warnings = capture_cli_probes(cli_section, project_root)
            warnings.extend(cli_warnings)
        elif only_probes is None:
            warnings.append("surface 'cli' is enabled but no probes are configured")

    api_section = pick("public_api", config.public_api) if config.public_api.enabled else None
    if api_section is not None:
        if api_section.probes:
            from .public_api import capture_api_probes

            surfaces["public_api"], api_warnings = capture_api_probes(
                api_section, project_root
            )
            warnings.extend(api_warnings)
        elif only_probes is None:
            warnings.append("surface 'public_api' is enabled but no probes are configured")

    js_section = pick("js_api", config.js_api) if config.js_api.enabled else None
    if js_section is not None:
        if js_section.probes:
            from .js_api import capture_js_api_probes

            surfaces["js_api"], js_warnings = capture_js_api_probes(
                js_section, project_root
            )
            warnings.extend(js_warnings)
        elif only_probes is None:
            warnings.append("surface 'js_api' is enabled but no probes are configured")

    # A probe that cannot run at all is not "no change": nothing was verified.
    # Surface it loudly here so it is visible at baseline time as well.
    for surface, captures in surfaces.items():
        for capture in captures:
            if not capture.ok:
                warnings.append(
                    f"probe {capture.target!r} failed to capture: "
                    f"{capture.error or 'unknown error'}"
                )

    project = detect_project(project_root)
    snapshot = Snapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        created_at=_now_iso(),
        tool_version=__version__,
        config_hash=config_hash(config),
        project=project.to_dict(),
        surfaces=surfaces,
        provenance={"git": collect_git_state(project_root)},
    )
    return snapshot, warnings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
