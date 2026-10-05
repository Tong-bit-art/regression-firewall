"""Structured behavior diffing."""

from __future__ import annotations

from ..config.schema import Config
from ..models.snapshot import Snapshot
from ..normalize.engine import Normalizer
from .engine import diff_json, json_type, make_change

SURFACE_ORDER = ("http", "cli", "public_api")

__all__ = ["diff_surfaces", "diff_json", "json_type", "make_change"]


def diff_surfaces(baseline: Snapshot, latest: Snapshot, normalizer: Normalizer,
                  config: Config) -> tuple:
    """Diff all surfaces. Returns (changes, warnings)."""
    from . import cli as cli_diff
    from . import http as http_diff
    from . import public_api as api_diff

    changes: list = []
    warnings: list = []
    for surface in SURFACE_ORDER:
        baseline_map = baseline.capture_map(surface)
        latest_map = latest.capture_map(surface)
        for probe_id in sorted(baseline_map):
            if probe_id not in latest_map:
                warnings.append(
                    f"probe {probe_id!r} exists in baseline but not in the latest capture; "
                    "the configuration changed between baseline and check"
                )
                continue
            before = baseline_map[probe_id]
            after = latest_map[probe_id]
            if surface == "http":
                changes.extend(http_diff.diff_http(before, after, normalizer, config, make_change))
            elif surface == "cli":
                changes.extend(cli_diff.diff_cli(before, after, normalizer, config, make_change))
            else:
                changes.extend(api_diff.diff_public_api(before, after, config, make_change))
        for probe_id in sorted(latest_map):
            if probe_id not in baseline_map:
                warnings.append(
                    f"probe {probe_id!r} exists in the latest capture but not in the baseline; "
                    "the configuration changed between baseline and check"
                )
    return changes, warnings
