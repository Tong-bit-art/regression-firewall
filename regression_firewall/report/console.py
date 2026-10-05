from __future__ import annotations

from ..models.change import is_missing
from ..models.result import CheckResult
from ..scoring.risk import severity_rank
from ._explain import recommended_action, why_it_matters

LINE = "─" * 64


def render_console(result: CheckResult) -> str:
    out = []
    out.append("Regression Firewall")
    out.append(LINE)

    project = result.project or {}
    out.append(f"Project: {project.get('name', '?')} ({project.get('language', '?')})")
    if result.intent_task:
        out.append(f"Intent: {result.intent_task}")
    elif result.intent_source != "none":
        out.append("Intent: (no task description given)")
    else:
        out.append("Intent: none provided — every change below is treated as unrequested")

    if result.config_changed_since_baseline:
        out.append("")
        out.append(
            "WARNING: the configuration changed since the baseline was captured. "
            "Re-run 'regression-firewall baseline' if this was intended."
        )
    if result.baseline_trust_warning:
        out.append("")
        out.append("BASELINE TRUST WARNING")
        out.append(
            "The baseline appears to have been captured after the working tree "
            "changed (its previous check reported a regression)."
        )
        out.append(
            "This may no longer represent pre-change behavior. Treat this result "
            "with reduced trust and confirm with the user."
        )
    for warning in result.warnings:
        out.append(f"WARNING: {warning}")

    summary = result.summary
    out.append("")
    out.append(
        f"Changes: {summary.get('expected', 0)} expected, "
        f"{summary.get('unexpected', 0)} unexpected, {summary.get('uncertain', 0)} uncertain"
    )

    expected = [c for c in result.changes if c.classification == "expected"]
    unexpected = [c for c in result.changes if c.classification != "expected"]

    if expected:
        out.append("")
        out.append("Expected Changes")
        for change in expected:
            out.append(f"  ✓ EXPECTED  {change.target}  {change.category}  {_transition(change)}")
            if change.note:
                out.append(f"      {change.note}")

    if unexpected:
        out.append("")
        out.append("Unexpected Changes")
        ordered = sorted(unexpected, key=lambda c: (-severity_rank(c.severity), c.target, c.category))
        for change in ordered:
            out.append("")
            out.append(f"  {change.severity.upper()}  {change.target}  {change.category}"
                       + (f"  [{change.path}]" if change.path else ""))
            out.append(f"      {_transition(change)}")
            out.append(f"      Why this matters: {why_it_matters(change.category)}")
            out.append(f"      Requested? {'yes' if change.classification == 'expected' else 'no evidence in intent'}")
            out.append(f"      Confidence: {int(round(change.confidence * 100))}%")

    out.append("")
    out.append(f"Risk Score: {result.score} / 100")
    out.append(f"Verdict: {result.verdict}")

    blocking = [c for c in unexpected if c.severity in ("high", "critical")
                and c.classification == "unexpected"]
    if result.verdict == "BLOCK":
        out.append(f"{len(blocking)} high-risk unintended change(s) detected.")
        if blocking:
            top = sorted(blocking, key=lambda c: -severity_rank(c.severity))[0]
            out.append("")
            out.append("Recommended action:")
            out.append(f"  {recommended_action(top.category)}")
    elif result.verdict == "REVIEW":
        out.append("Changes need human review before the task can be called complete.")

    return "\n".join(out)


def _transition(change) -> str:
    before = _fmt(change.before, change.evidence)
    after = _fmt(change.after, change.evidence)
    return f"{before} -> {after}"


def _fmt(value, evidence: dict) -> str:
    if is_missing(value) or value is None:
        return "<absent>"
    if isinstance(value, str):
        text = value.replace("\n", "\\n")
        return text if len(text) <= 60 else text[:57] + "..."
    if isinstance(value, (dict, list)):
        import json

        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return text if len(text) <= 60 else text[:57] + "..."
    return str(value)
