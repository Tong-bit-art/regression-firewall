from regression_firewall.intent.audit import (changed_since, compute_audit,
                                              entry_fingerprint, entry_key,
                                              pending_fingerprints)
from regression_firewall.intent.model import ExpectedChange


def make_entry(**kw):
    base = dict(surface="http", target="POST /login", category="status_changed")
    base.update(kw)
    return ExpectedChange(**base)


def state(entries):
    return {
        "exists": True,
        "path": "intent.json",
        "hash": "x",
        "entries": [
            {"key": entry_key(e), "fingerprint": entry_fingerprint(e)}
            for e in entries
        ],
    }


def test_entry_key_and_fingerprint_are_stable():
    entry = make_entry(before=401, after=423, note="lockout")
    assert entry_key(entry) == "http|POST /login|status_changed"
    reordered = make_entry(after=423, before=401, note="lockout")
    assert entry_fingerprint(entry) == entry_fingerprint(reordered)
    changed = make_entry(before=401, after=500, note="lockout")
    assert entry_fingerprint(entry) != entry_fingerprint(changed)


def test_changed_since_detects_added_and_modified():
    reference = state([make_entry(before=401, after=423)])
    added = state([make_entry(before=401, after=423),
                   make_entry(before=200, after=400)])
    assert [e["key"] for e in changed_since(added, reference)] == [
        "http|POST /login|status_changed"]

    modified = state([make_entry(before=401, after=400)])
    assert len(changed_since(modified, reference)) == 1  # same key, new fingerprint


def test_baseline_window_entries_are_not_post_hoc():
    baseline = {"baseline_id": "b1", "intent_at_baseline": state([])}
    audit = compute_audit(state([make_entry()]), baseline, None, accept=False)
    assert audit["previous"]["source"] == "baseline"
    assert audit["post_hoc_entries"] == []
    assert audit["changed_since_baseline"] == ["http|POST /login|status_changed"]


def test_post_hoc_entries_are_cumulative_until_accepted():
    entry = make_entry()
    baseline = {"baseline_id": "b1", "intent_at_baseline": state([])}
    first_report = {
        "verdict": "BLOCK",
        "intent_audit": {"baseline_id": "b1", "intent_at_check": state([]),
                         "post_hoc_entries": [], "accepted_entries": []},
    }
    audit = compute_audit(state([entry]), baseline, first_report, accept=False)
    assert audit["previous"]["source"] == "previous-check"
    assert audit["previous"]["verdict"] == "BLOCK"
    assert [e["key"] for e in audit["post_hoc_entries"]] == [
        "http|POST /login|status_changed"]
    assert pending_fingerprints(audit)

    # Re-running with unchanged intent keeps the entry pending.
    again = compute_audit(state([entry]), baseline,
                          {"verdict": "REVIEW", "intent_audit": audit}, accept=False)
    assert [e["key"] for e in again["post_hoc_entries"]] == [
        "http|POST /login|status_changed"]

    accepted = compute_audit(state([entry]), baseline,
                             {"verdict": "REVIEW", "intent_audit": again}, accept=True)
    assert accepted["post_hoc_entries"] == []
    assert accepted["post_hoc_accepted"] is True

    final = compute_audit(state([entry]), baseline,
                          {"verdict": "PASS", "intent_audit": accepted}, accept=False)
    assert final["post_hoc_entries"] == []
    assert final["post_hoc_accepted"] is False


def test_new_baseline_resets_the_audit_window():
    baseline = {"baseline_id": "b2", "intent_at_baseline": state([])}
    old_report = {
        "verdict": "REVIEW",
        "intent_audit": {"baseline_id": "b1",
                         "intent_at_check": state([]),
                         "post_hoc_entries": [{"key": "k", "fingerprint": "fp"}],
                         "accepted_entries": []},
    }
    audit = compute_audit(state([make_entry()]), baseline, old_report, accept=False)
    assert audit["previous"]["source"] == "baseline"
    assert audit["post_hoc_entries"] == []
