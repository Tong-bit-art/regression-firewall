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

    # -- traced behavior footprint (probe.trace; Python commands) ------------

    # Write paths are normalized (temp dirs masked) before comparison; env
    # var NAMES are compared raw — masking a name like API_TOKEN would
    # destroy exactly the signal this category exists for.
    fs_before = {normalizer.normalize_string(p) for p in (bd.get("fs_writes") or [])}
    fs_after = {normalizer.normalize_string(p) for p in (ad.get("fs_writes") or [])}
    for path in sorted(fs_before - fs_after):
        changes.append(make_change(
            "cli", after.target, "fs_write_removed", path=path,
            before=path, after=MISSING,
            description=f"{after.target}: no longer writes to '{path}'",
            config=config,
        ))
    for path in sorted(fs_after - fs_before):
        changes.append(make_change(
            "cli", after.target, "fs_write_added", path=path,
            before=MISSING, after=path,
            description=f"{after.target}: now also writes to '{path}'",
            config=config,
        ))

    env_before = set(bd.get("env_reads") or [])
    env_after = set(ad.get("env_reads") or [])
    for name in sorted(env_before - env_after):
        changes.append(make_change(
            "cli", after.target, "env_read_removed", path=name,
            before=name, after=MISSING,
            description=f"{after.target}: no longer reads environment variable '{name}'",
            config=config,
        ))
    for name in sorted(env_after - env_before):
        changes.append(make_change(
            "cli", after.target, "env_read_added", path=name,
            before=MISSING, after=name,
            description=f"{after.target}: now reads environment variable '{name}'",
            config=config,
        ))

    # -- database footprint (trace.sqlite; stdlib sqlite3) --------------------

    # Shapes are normalized at capture time (literals -> placeholders), so a
    # data change never looks like a query-set change. Counts ARE compared,
    # but as a LOW/uncertain signal: legitimate loop bounds move them too.
    db_before = bd.get("db_queries") or {}
    db_after = ad.get("db_queries") or {}
    for shape in sorted(set(db_before) - set(db_after)):
        changes.append(make_change(
            "cli", after.target, "db_query_removed", path=shape,
            before={"count": db_before[shape]}, after=MISSING,
            description=f"{after.target}: no longer runs {shape}",
            config=config,
        ))
    for shape in sorted(set(db_after) - set(db_before)):
        changes.append(make_change(
            "cli", after.target, "db_query_added", path=shape,
            before=MISSING, after={"count": db_after[shape]},
            description=f"{after.target}: now also runs {shape}",
            config=config,
        ))
    for shape in sorted(set(db_before) & set(db_after)):
        if db_before[shape] != db_after[shape]:
            changes.append(make_change(
                "cli", after.target, "db_query_count_changed", path=shape,
                before=db_before[shape], after=db_after[shape],
                description=(f"{after.target}: runs {shape} "
                             f"{db_before[shape]} -> {db_after[shape]} time(s)"),
                config=config,
            ))

    tables_before = set(bd.get("db_tables_written") or [])
    tables_after = set(ad.get("db_tables_written") or [])
    for table in sorted(tables_before - tables_after):
        changes.append(make_change(
            "cli", after.target, "db_table_written_removed", path=table,
            before=table, after=MISSING,
            description=f"{after.target}: no longer writes table '{table}'",
            config=config,
        ))
    for table in sorted(tables_after - tables_before):
        changes.append(make_change(
            "cli", after.target, "db_table_written_added", path=table,
            before=MISSING, after=table,
            description=f"{after.target}: now also writes table '{table}'",
            config=config,
        ))

    # -- opt-in runtime measurement (probe.performance) -----------------------

    median_before = bd.get("runtime_median_ms")
    median_after = ad.get("runtime_median_ms")
    if median_before and median_after:
        ratio = median_after / median_before
        perf = (getattr(config, "cli", None) and _probe_performance(config, after.probe_id)) or {}
        max_ratio = float(perf.get("max_ratio", 2.0))
        if ratio > max_ratio:
            changes.append(make_change(
                "cli", after.target, "runtime_regressed",
                before={"median_ms": median_before},
                after={"median_ms": median_after},
                evidence={"ratio": round(ratio, 3), "max_ratio": max_ratio,
                          "runs_baseline": bd.get("runtime_runs"),
                          "runs_check": ad.get("runtime_runs")},
                description=(f"{after.target}: median runtime {median_before}ms -> "
                             f"{median_after}ms ({ratio:.2f}x > {max_ratio}x budget)"),
                config=config,
            ))

    return changes


def _probe_performance(config, probe_id: str) -> dict:
    for probe in config.cli.probes:
        if probe.id == probe_id and probe.performance:
            return {"max_ratio": probe.performance.max_ratio}
    return {}


def _preview(value) -> str:
    text = str(value or "")
    return text if len(text) <= 200 else text[:197] + "..."
