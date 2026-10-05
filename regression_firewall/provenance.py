"""Baseline provenance: git working-tree state and snapshot integrity hashes.

Git is optional: outside a repository (or without git installed) the fields
are recorded as absent instead of failing the capture.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

GIT_TIMEOUT = 10.0


def collect_git_state(project_root: Path) -> dict:
    """Returns {git_available, git_commit, git_dirty} for the project root."""
    state = {"git_available": False, "git_commit": None, "git_dirty": None}
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(project_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return state
    except (OSError, subprocess.TimeoutExpired):
        return state

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(project_root), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(project_root), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT,
    )
    state["git_available"] = True
    state["git_commit"] = commit.stdout.strip() if commit.returncode == 0 else None
    state["git_dirty"] = bool(status.stdout.strip())
    return state


def content_hash(snapshot_dict: dict) -> str:
    """Integrity hash over the snapshot's captured content (excludes
    provenance and timestamps so a re-check of identical behavior matches)."""
    payload = {
        "schema_version": snapshot_dict.get("schema_version"),
        "project": snapshot_dict.get("project"),
        "surfaces": snapshot_dict.get("surfaces"),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
