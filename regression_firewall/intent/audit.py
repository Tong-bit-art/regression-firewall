"""Intent audit trail — detects post-hoc intent edits.

The agent contract (SKILL.md) says intent describes what the *user asked for*
and is written before ``check``. The tool cannot observe code edits, but it
can observe intent-file state at baseline time and at every check. This
module records those states and detects the "post-hoc intent" pattern:

    the agent sees BLOCK/REVIEW (or simply the check output), adds or edits
    an intent entry, re-runs check, and the previously unexpected change is
    now silently classified as EXPECTED.

A lightweight, honest rule is possible from data the tool already has:

- a new baseline starts a fresh audit window (``baseline_id``);
- within one baseline window, an intent entry that first appears in a *later*
  check than the check that already observed the behavior is POST-HOC;
- post-hoc entries are cumulative: they stay pending across checks until the
  user explicitly acknowledges them with ``--accept-post-hoc-intent`` (or the
  entry is removed / a new baseline is taken);
- pending post-hoc entries can never turn a check into a clean PASS on their
  own: matched changes are annotated, warned about, and the verdict is kept
  at REVIEW.

Limitation (documented): the tool cannot know when the implementation was
edited. It anchors on the previous check run, which is the strongest signal
available; intent written before the first check of a baseline window is
treated as pre-implementation intent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .model import Intent


def entry_canonical(entry) -> dict:
    return {
        "surface": entry.surface,
        "target": entry.target,
        "category": entry.category,
        "path": entry.path,
        "before": entry.before,
        "after": entry.after,
        "note": entry.note,
    }


def entry_fingerprint(entry) -> str:
    canonical = json.dumps(entry_canonical(entry), sort_keys=True,
                           ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def entry_key(entry) -> str:
    parts = [str(entry.surface), str(entry.target), str(entry.category)]
    if entry.path:
        parts.append(str(entry.path))
    return "|".join(parts)


def intent_state(intent: Intent, path) -> dict:
    """Serializable audit snapshot of one intent file state."""
    entries = [
        {"key": entry_key(entry), "fingerprint": entry_fingerprint(entry)}
        for entry in intent.expected_changes
    ]
    digest = hashlib.sha256(
        json.dumps(sorted(e["fingerprint"] for e in entries)).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "exists": bool(path) and Path(path).is_file(),
        "path": str(path) if path else None,
        "hash": digest,
        "entries": entries,
    }


def load_intent_state(path) -> dict:
    """Audit snapshot for a path, loading the intent file if it exists."""
    from .model import load_intent

    if path is None or not Path(path).is_file():
        return intent_state(Intent(), path)
    return intent_state(load_intent(Path(path)), path)


JOURNAL_NAME = "intent_audit.jsonl"


def append_journal(artifacts: Path, entry: dict) -> None:
    """Append one audit event. Best-effort: the report remains the primary
    artifact, the journal is redundancy against a deleted/rotated report."""
    try:
        with (artifacts / JOURNAL_NAME).open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def last_check_from_journal(artifacts: Path, baseline_id) -> dict | None:
    """Latest ``check`` journal event for this baseline, if any."""
    path = Path(artifacts) / JOURNAL_NAME
    if not path.is_file():
        return None
    last = None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") == "check" and record.get("baseline_id") == baseline_id:
                last = record
    except OSError:
        return None
    return last


def changed_since(current: dict, reference: dict) -> list:
    """Entries in ``current`` whose fingerprint is not in ``reference``."""
    known = {e.get("fingerprint") for e in (reference or {}).get("entries") or []}
    return [e for e in (current or {}).get("entries") or []
            if e.get("fingerprint") not in known]


def resolve_previous(baseline_provenance: dict, previous_report: dict | None,
                     journal_check: dict | None = None) -> tuple:
    """Returns (source, verdict, state, previous_audit) for the audit window.

    A previous report only counts when it belongs to the same baseline
    (``baseline_id``); otherwise a matching journal entry is used, and only
    then the baseline itself is the reference. ``previous_audit`` always
    belongs to the source that was actually used (so cumulative pending
    entries survive a deleted report.json via the journal).
    """
    baseline_id = (baseline_provenance or {}).get("baseline_id")
    baseline_state = (baseline_provenance or {}).get("intent_at_baseline")
    if previous_report:
        audit = previous_report.get("intent_audit") or {}
        if baseline_id and audit.get("baseline_id") == baseline_id:
            state = audit.get("intent_at_check")
            if state is not None:
                return "previous-check", previous_report.get("verdict"), state, audit
    if journal_check and baseline_id and journal_check.get("baseline_id") == baseline_id:
        state = journal_check.get("intent")
        if state is not None:
            return "previous-check", journal_check.get("verdict"), state, journal_check
    if baseline_state is not None:
        return "baseline", None, baseline_state, {}
    return "none", None, {"exists": False, "entries": []}, {}


def compute_audit(current: dict, baseline_provenance: dict,
                  previous_report: dict | None, accept: bool,
                  journal_check: dict | None = None) -> dict:
    """Build the ``intent_audit`` block for a check report.

    Returns the serializable audit dict. Call ``pending_fingerprints`` on the
    result to get the fingerprints that guard expected classification.
    """
    source, previous_verdict, reference, prev_audit = resolve_previous(
        baseline_provenance, previous_report, journal_check)

    changed_baseline = changed_since(current, (baseline_provenance or {})
                                     .get("intent_at_baseline") or {})
    changed_previous = changed_since(current, reference) if source == "previous-check" else []

    prev_pending = prev_audit.get("post_hoc_entries") or []
    prev_accepted = prev_audit.get("accepted_entries") or []
    accepted_fps = {e.get("fingerprint") for e in prev_accepted}
    current_fps = {e.get("fingerprint") for e in current.get("entries") or []}

    if source == "previous-check":
        # Pending entries are cumulative within a baseline window; entries no
        # longer present in intent (or already accepted) drop out.
        pending = [e for e in prev_pending
                   if e.get("fingerprint") in current_fps
                   and e.get("fingerprint") not in accepted_fps]
        pending_fps = {e.get("fingerprint") for e in pending}
        for entry in changed_previous:
            if entry.get("fingerprint") not in pending_fps:
                pending.append(entry)
    else:
        pending = []

    accepted_now = []
    if pending and accept:
        accepted_now = [dict(e) for e in pending]
        pending = []
        accepted_fps = accepted_fps | {e.get("fingerprint") for e in accepted_now}

    accepted_entries = [dict(e) for e in prev_accepted
                        if e.get("fingerprint") in current_fps]
    for entry in accepted_now:
        if entry.get("fingerprint") not in {e.get("fingerprint") for e in accepted_entries}:
            accepted_entries.append(entry)

    return {
        "baseline_id": (baseline_provenance or {}).get("baseline_id"),
        "intent_at_check": current,
        "previous": {"source": source, "verdict": previous_verdict},
        "changed_since_baseline": [e.get("key") for e in changed_baseline],
        "changed_since_previous": [e.get("key") for e in changed_previous],
        "post_hoc_entries": pending,
        "post_hoc_pending": False,  # set by the caller once matches are known
        "post_hoc_accepted": bool(accepted_now),
        "accepted_entries": accepted_entries,
    }


def pending_fingerprints(audit: dict) -> set:
    return {e.get("fingerprint") for e in audit.get("post_hoc_entries") or []}
