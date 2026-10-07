from __future__ import annotations

from ..models.change import is_missing
from ..models.result import CheckResult
from ..scoring.risk import severity_rank
from ._explain import recommended_action, why_it_matters


def render_markdown(result: CheckResult) -> str:
    out = []
    out.append("# Regression Firewall Report")
    out.append("")
    project = result.project or {}
    out.append(f"- **Project:** {project.get('name', '?')} ({project.get('language', '?')})")
    out.append(f"- **Generated:** {result.created_at}")
    out.append(f"- **Tool:** regression-firewall {result.tool_version}")
    out.append(f"- **Verdict:** **{result.verdict}**")
    out.append(f"- **Risk score:** {result.score} / 100"
               + (" (floored to match verdict rules)" if result.score_floored else ""))
    if result.intent_task:
        out.append(f"- **Intent:** {result.intent_task}")
    if result.intent_source == "none":
        out.append("- **Intent:** none provided — all changes below are treated as unrequested")
    out.append("")

    summary = result.summary
    out.append(
        f"**Summary:** {summary.get('expected', 0)} expected, "
        f"{summary.get('unexpected', 0)} unexpected, {summary.get('uncertain', 0)} uncertain."
    )
    out.append("")

    for warning in result.warnings:
        out.append(f"> ⚠️ {warning}")
        out.append("")
    if result.config_changed_since_baseline:
        out.append("> ⚠️ The configuration changed since the baseline was captured; "
                   "re-baseline if this was intended.")
        out.append("")
    if result.baseline_trust_warning:
        out.append("> **BASELINE TRUST WARNING**: the baseline appears to have been "
                   "captured after the working tree changed (its previous check "
                   "reported a regression). It may no longer represent pre-change "
                   "behavior; treat this result with reduced trust.")
        out.append("")

    unexpected = sorted(
        (c for c in result.changes if c.classification != "expected"),
        key=lambda c: (-severity_rank(c.severity), c.target, c.category),
    )
    expected = [c for c in result.changes if c.classification == "expected"]

    if unexpected:
        out.append("## Unexpected Changes")
        out.append("")
        for change in unexpected:
            title = change.path or change.target
            out.append(f"### {change.severity.upper()} — {change.target} — {change.category}")
            if change.path and change.path != change.target:
                out.append(f"**Location:** `{change.path}`")
            out.append("")
            out.append(f"| | |")
            out.append(f"|---|---|")
            out.append(f"| Before | `{_fmt(change.before)}` |")
            out.append(f"| After | `{_fmt(change.after)}` |")
            out.append(f"| Requested | no evidence in intent |")
            out.append(f"| Confidence | {int(round(change.confidence * 100))}% |")
            out.append("")
            out.append(f"**Why this matters:** {why_it_matters(change.category)}")
            out.append("")
            out.append(f"**What to verify:** {recommended_action(change.category)}")
            out.append("")

    if expected:
        out.append("## Expected Changes (matched intent)")
        out.append("")
        out.append("| Target | Category | Transition | Note | Basis |")
        out.append("|---|---|---|---|---|")
        for change in expected:
            basis = ("**POST-HOC — not part of the original declared scope; "
                     "needs explicit user confirmation**" if change.post_hoc
                     else "declared before the change")
            out.append(
                f"| {change.target} | {change.category} "
                f"| {_fmt(change.before)} → {_fmt(change.after)} | {change.note or ''} | {basis} |"
            )
        out.append("")

    audit = result.intent_audit or {}
    if audit:
        prev = audit.get("previous") or {}
        out.append("## Intent Audit")
        out.append("")
        out.append(f"- Baseline id: `{audit.get('baseline_id')}`")
        out.append(f"- Previous reference: {prev.get('source')}"
                   + (f" (verdict {prev.get('verdict')})" if prev.get("verdict") else ""))
        out.append(f"- Entries added/modified since baseline: "
                   f"{len(audit.get('changed_since_baseline') or [])}")
        out.append(f"- Entries added/modified since previous check: "
                   f"{len(audit.get('changed_since_previous') or [])}")
        pending = audit.get("post_hoc_entries") or []
        if pending:
            out.append(f"- **Pending post-hoc entries: "
                       f"{', '.join(e.get('key') or '?' for e in pending)}**")
        if audit.get("post_hoc_accepted"):
            out.append("- Post-hoc entries were **accepted** via "
                       "`--accept-post-hoc-intent` in this run.")
        out.append("")

    if not unexpected and not expected:
        out.append("No behavior changes were detected.")
        out.append("")

    out.append("---")
    out.append(
        "*Generated by Regression Firewall. `BLOCK` means the task should not be "
        "declared complete until the reported changes are fixed or confirmed intentional.*"
    )
    return "\n".join(out)


def _fmt(value) -> str:
    if is_missing(value) or value is None:
        return "&lt;absent&gt;"
    if isinstance(value, str):
        text = value.replace("\n", "\\n").replace("|", "\\|")
        return text if len(text) <= 60 else text[:57] + "..."
    if isinstance(value, (dict, list)):
        import json

        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return text if len(text) <= 60 else text[:57] + "..."
    return str(value)
