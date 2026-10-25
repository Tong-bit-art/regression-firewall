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
CHANGED_FILES_CAP = 200


def collect_changed_files(project_root: Path, base_commit, current_dirty: bool = None) -> dict:
    """Files changed since the baseline commit: committed diffs plus, when the
    current tree is dirty, the modified/untracked files from status.

    This is a correlation HINT for reports — it never affects classification,
    scoring, or the verdict. Returns {available, files, truncated}.
    """
    result = {"available": False, "files": [], "truncated": False}
    if not base_commit:
        return result
    try:
        diff = subprocess.run(
            ["git", "diff", "--name-only", f"{base_commit}..HEAD"],
            cwd=str(project_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT,
        )
        if diff.returncode != 0:
            return result
        files = [line.strip() for line in diff.stdout.splitlines() if line.strip()]
        if current_dirty:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(project_root), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT,
            )
            if status.returncode == 0:
                files.extend(_porcelain_paths(status.stdout))
        unique = sorted(
            f for f in set(files) if not f.startswith(".regression-firewall")
        )
        if len(unique) > CHANGED_FILES_CAP:
            unique = unique[:CHANGED_FILES_CAP]
            result["truncated"] = True
        result["available"] = True
        result["files"] = unique
        return result
    except (OSError, subprocess.TimeoutExpired):
        return result


def _porcelain_paths(status_output: str) -> list:
    """Parse `git status --porcelain` output into paths. Handles renames
    ('R  old -> new' → the new path) and the quoting git applies to paths
    with special characters."""
    paths = []
    for line in status_output.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip().strip('"')
        if path:
            paths.append(path)
    return paths


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
