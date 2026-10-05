from __future__ import annotations

from ..config.schema import Config
from ..models.change import MISSING
from ..models.snapshot import ProbeCapture
from ..normalize.engine import Normalizer


def diff_cli(before: ProbeCapture, after: ProbeCapture, normalizer: Normalizer,
             config: Config, make_change) -> list:
    changes = []

    if before.ok != after.ok:
        changes.append(make_change(
            "cli", after.target, "capture_error",
            before=before.error or "captured ok",
            after=after.error or "captured ok",
            description=(f"{after.target}: command was {'failing' if not before.ok else 'running'} "
                         f"at baseline and is now {'failing' if not after.ok else 'running'}"),
            config=config,
        ))
        return changes

    bd, ad = before.data or {}, after.data or {}
    exit_before, exit_after = bd.get("exit_code"), ad.get("exit_code")
    if exit_before != exit_after:
        severity = "high" if exit_before == 0 and exit_after != 0 else "medium"
        changes.append(make_change(
            "cli", after.target, "exit_code_changed",
            before=exit_before, after=exit_after,
            description=f"{after.target}: exit code {exit_before} -> {exit_after}",
            severity=severity, config=config,
        ))

    stdout_before = normalizer.normalize_text(str(bd.get("stdout") or ""))
    stdout_after = normalizer.normalize_text(str(ad.get("stdout") or ""))
    if stdout_before != stdout_after:
        changes.append(make_change(
            "cli", after.target, "stdout_changed",
            before=_preview(normalizer.normalize_text(str(bd.get("stdout") or ""))),
            after=_preview(normalizer.normalize_text(str(ad.get("stdout") or ""))),
            description=f"{after.target}: stdout changed",
            config=config,
        ))

    stderr_before = normalizer.normalize_text(str(bd.get("stderr") or ""))
    stderr_after = normalizer.normalize_text(str(ad.get("stderr") or ""))
    if stderr_before != stderr_after:
        changes.append(make_change(
            "cli", after.target, "stderr_changed",
            before=_preview(normalizer.normalize_text(str(bd.get("stderr") or ""))),
            after=_preview(normalizer.normalize_text(str(ad.get("stderr") or ""))),
            description=f"{after.target}: stderr changed",
            config=config,
        ))

    files_before = bd.get("files") or {}
    files_after = ad.get("files") or {}
    for rel_path in sorted(set(files_before) | set(files_after)):
        entry_before = files_before.get(rel_path) or {"exists": False}
        entry_after = files_after.get(rel_path) or {"exists": False}
        existed_before = bool(entry_before.get("exists"))
        existed_after = bool(entry_after.get("exists"))
        if existed_before and not existed_after:
            changes.append(make_change(
                "cli", after.target, "file_deleted", path=rel_path,
                before={"size": entry_before.get("size")}, after=MISSING,
                description=f"{after.target}: generated file '{rel_path}' is now missing",
                config=config,
            ))
        elif not existed_before and existed_after:
            changes.append(make_change(
                "cli", after.target, "file_created", path=rel_path,
                before=MISSING,
                after={"size": entry_after.get("size"), "sha256": entry_after.get("sha256")},
                description=f"{after.target}: generated file '{rel_path}' is new",
                config=config,
            ))
        elif existed_before and existed_after:
            if entry_before.get("sha256") != entry_after.get("sha256"):
                changes.append(make_change(
                    "cli", after.target, "file_modified", path=rel_path,
                    before={"sha256": entry_before.get("sha256"), "size": entry_before.get("size")},
                    after={"sha256": entry_after.get("sha256"), "size": entry_after.get("size")},
                    description=f"{after.target}: generated file '{rel_path}' content changed",
                    config=config,
                ))

    return changes


def _preview(value) -> str:
    text = str(value or "")
    return text if len(text) <= 200 else text[:197] + "..."
