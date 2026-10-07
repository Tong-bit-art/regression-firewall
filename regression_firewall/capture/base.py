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


def run_capture(config: Config, project_root: Path, artifacts_dir: Path) -> tuple:
    """Run all enabled, configured probes.

    Returns (Snapshot, warnings).
    """
    warnings: list = []
    surfaces: dict = {}

    if config.http.enabled:
        if config.http.probes:
            from .http_probe import capture_http_probes

            surfaces["http"], http_warnings = capture_http_probes(
                config.http, project_root, artifacts_dir, config.redaction
            )
            warnings.extend(http_warnings)
        else:
            warnings.append("surface 'http' is enabled but no probes are configured")

    if config.cli.enabled:
        if config.cli.probes:
            from .cli import capture_cli_probes

            surfaces["cli"], cli_warnings = capture_cli_probes(config.cli, project_root)
            warnings.extend(cli_warnings)
        else:
            warnings.append("surface 'cli' is enabled but no probes are configured")

    if config.public_api.enabled:
        if config.public_api.probes:
            from .public_api import capture_api_probes

            surfaces["public_api"], api_warnings = capture_api_probes(
                config.public_api, project_root
            )
            warnings.extend(api_warnings)
        else:
            warnings.append("surface 'public_api' is enabled but no probes are configured")

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
