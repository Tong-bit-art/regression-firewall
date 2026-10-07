"""Benchmark mutation engine: verified find/replace patches on real code."""

from __future__ import annotations

from pathlib import Path


def apply_mutation(project_root: Path, edits: list) -> None:
    """Apply one mutation's edits (list of {file, find, replace}).

    Raises MutationError if any find-string is missing — an authoring error,
    never a benchmark result.
    """
    for edit in edits:
        path = project_root / edit["file"]
        if not path.is_file():
            raise MutationError(f"file not found: {edit['file']}")
        text = path.read_text(encoding="utf-8", errors="strict")
        if edit["find"] not in text:
            raise MutationError(
                f"find-string not found in {edit['file']}: {edit['find'][:80]!r}"
            )
        # replace_all: true replaces every occurrence (e.g. the same error
        # call appears in two decorators); default is the first occurrence.
        count = -1 if edit.get("replace_all") else 1
        path.write_text(text.replace(edit["find"], edit["replace"], count),
                        encoding="utf-8", newline="\n")


def restore(project_root: Path, repo_root: Path, excludes: list | None = None) -> None:
    """Restore the working tree to the pinned-commit state, keeping the
    benchmark config, the tool's artifacts dir, and repo-provided excludes
    (e.g. generated databases) intact."""
    run = _git(["checkout", "--", "."], repo_root)
    if run.returncode != 0:
        raise MutationError(f"git checkout failed: {run.stderr[:200]}")
    excludes = excludes or []
    # -x: also remove ignored files (e.g. *.txt matched by repo .gitignore) —
    # without -x, mutation-generated files persist and corrupt baselines
    clean_args = ["clean", "-fdqx"]
    for pattern in excludes + [".regression-firewall", ".regression-firewall.yml"]:
        clean_args += ["--exclude", pattern]
    clean = _git(clean_args, project_root if project_root.exists() else repo_root)
    if clean.returncode != 0:
        raise MutationError(f"git clean failed: {clean.stderr[:200]}")


def _git(args: list, cwd: Path):
    import subprocess

    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60)


class MutationError(RuntimeError):
    pass
