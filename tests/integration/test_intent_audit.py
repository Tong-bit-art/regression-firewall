"""P0 intent audit immutability: the check-after-BLOCK intent edit.

A coding agent must not be able to turn an already-observed, unexpected
change into EXPECTED by adding an intent entry after the check saw it. The
audit trail records intent state per baseline and per check; entries that
first appear after a previous check observed the behavior are POST-HOC and
stay pending (verdict kept at REVIEW) until explicitly acknowledged with
--accept-post-hoc-intent.
"""

import json

API_CONFIG = """\
version: 1
surfaces:
  http:
    enabled: false
  cli:
    enabled: false
  public_api:
    enabled: true
    probes:
      - id: samplelib
        module: samplelib
"""

LIB_V1 = """\
class Client:
    def __init__(self, retries=3):
        self.retries = retries


class RetryPolicy:
    def __init__(self, attempts=5):
        self.attempts = attempts


def connect(host, port=5432):
    return (host, port)
"""

LIB_WITHOUT_RETRYPOLICY = LIB_V1.replace('''class RetryPolicy:
    def __init__(self, attempts=5):
        self.attempts = attempts


''', "")


def read_report(project):
    return json.loads(
        (project / ".regression-firewall" / "report.json").read_text(encoding="utf-8")
    )


def write_intent(project, write, entries, task="requested change"):
    write(project / ".regression-firewall" / "intent.json",
          json.dumps({"schema_version": 1, "task": task,
                      "expected_changes": entries}, indent=2))


def setup_lib(project, run_rf, write):
    write(project / "samplelib" / "__init__.py", LIB_V1)
    write(project / ".regression-firewall.yml", API_CONFIG)
    run_rf(["baseline"], project, expect_exit=0)


def test_intent_written_before_first_check_is_not_post_hoc(project, run_rf, write):
    """The normal workflow (baseline -> intent -> edit -> check) is unchanged:
    first-check intent entries are pre-implementation and PASS normally."""
    setup_lib(project, run_rf, write)
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.RetryPolicy",
         "category": "symbol_removed", "note": "intentional removal"},
    ])
    write(project / "samplelib" / "__init__.py", LIB_WITHOUT_RETRYPOLICY)

    proc = run_rf(["check"], project)
    assert proc.returncode == 0, proc.stdout
    report = read_report(project)
    assert report["verdict"] == "PASS"
    audit = report["intent_audit"]
    assert audit["previous"]["source"] == "baseline"
    assert audit["post_hoc_entries"] == []
    assert audit["changed_since_baseline"] == ["public_api|samplelib.RetryPolicy|symbol_removed"]


def test_post_hoc_intent_after_block_holds_review(project, run_rf, write):
    setup_lib(project, run_rf, write)
    write(project / "samplelib" / "__init__.py", LIB_WITHOUT_RETRYPOLICY)
    first = run_rf(["check"], project)
    assert first.returncode == 3, first.stdout  # BLOCK: unexpected removal

    # The agent now adds the intent entry *after* the check observed it.
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.RetryPolicy",
         "category": "symbol_removed", "note": "intentional removal"},
    ])
    proc = run_rf(["check"], project)
    assert proc.returncode == 1, proc.stdout  # REVIEW, not PASS

    report = read_report(project)
    assert report["verdict"] == "REVIEW"
    audit = report["intent_audit"]
    assert audit["previous"]["source"] == "previous-check"
    assert audit["previous"]["verdict"] == "BLOCK"
    assert audit["post_hoc_pending"] is True
    assert [e["key"] for e in audit["post_hoc_entries"]] == [
        "public_api|samplelib.RetryPolicy|symbol_removed"]
    assert any("POST-HOC INTENT WARNING" in w for w in report["warnings"])
    change = report["changes"][0]
    assert change["classification"] == "expected"
    assert change["post_hoc"] is True


def test_post_hoc_stays_pending_until_accepted(project, run_rf, write):
    setup_lib(project, run_rf, write)
    write(project / "samplelib" / "__init__.py", LIB_WITHOUT_RETRYPOLICY)
    run_rf(["check"], project, expect_exit=3)
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.RetryPolicy",
         "category": "symbol_removed", "note": "intentional removal"},
    ])
    run_rf(["check"], project, expect_exit=1)

    # Re-running does not launder the pending entry: still REVIEW.
    again = run_rf(["check"], project)
    assert again.returncode == 1, again.stdout
    assert read_report(project)["intent_audit"]["post_hoc_pending"] is True

    accepted = run_rf(["check", "--accept-post-hoc-intent"], project)
    assert accepted.returncode == 0, accepted.stdout
    report = read_report(project)
    assert report["verdict"] == "PASS"
    assert report["intent_audit"]["post_hoc_accepted"] is True
    assert report["intent_audit"]["post_hoc_entries"] == []
    assert report["changes"][0]["post_hoc"] is False

    # Acceptance sticks: later checks are clean.
    clean = run_rf(["check"], project)
    assert clean.returncode == 0, clean.stdout
    assert read_report(project)["intent_audit"]["post_hoc_entries"] == []


def test_modified_entry_after_block_is_post_hoc(project, run_rf, write):
    setup_lib(project, run_rf, write)
    write(project / "samplelib" / "__init__.py", LIB_WITHOUT_RETRYPOLICY)

    # Entry exists at the first check but does not match (wrong constraint).
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.RetryPolicy",
         "category": "symbol_removed", "before": "something-else"},
    ])
    first = run_rf(["check"], project)
    assert first.returncode == 3, first.stdout  # BLOCK

    # The entry is *modified* after the check observed the removal.
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.RetryPolicy",
         "category": "symbol_removed"},
    ])
    proc = run_rf(["check"], project)
    assert proc.returncode == 1, proc.stdout  # REVIEW: modified after observation
    audit = read_report(project)["intent_audit"]
    assert [e["key"] for e in audit["post_hoc_entries"]] == [
        "public_api|samplelib.RetryPolicy|symbol_removed"]
    assert audit["changed_since_previous"] == [
        "public_api|samplelib.RetryPolicy|symbol_removed"]


def test_new_baseline_starts_fresh_audit_window(project, run_rf, write):
    setup_lib(project, run_rf, write)
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.RetryPolicy",
         "category": "symbol_removed"},
    ])
    write(project / "samplelib" / "__init__.py", LIB_WITHOUT_RETRYPOLICY)
    run_rf(["check"], project, expect_exit=0)

    # Next task: fresh baseline (previous verdict PASS), fresh intent.
    run_rf(["baseline"], project, expect_exit=0)
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.extra",
         "category": "symbol_added"},
    ])
    mutated = LIB_WITHOUT_RETRYPOLICY + """


def extra():
    return "extra"
"""
    write(project / "samplelib" / "__init__.py", mutated)

    proc = run_rf(["check"], project)
    assert proc.returncode == 0, proc.stdout
    audit = read_report(project)["intent_audit"]
    assert audit["previous"]["source"] == "baseline"
    assert audit["post_hoc_entries"] == []


def test_accept_without_pending_entries_is_clean(project, run_rf, write):
    setup_lib(project, run_rf, write)
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.RetryPolicy",
         "category": "symbol_removed"},
    ])
    write(project / "samplelib" / "__init__.py", LIB_WITHOUT_RETRYPOLICY)
    proc = run_rf(["check", "--accept-post-hoc-intent"], project)
    assert proc.returncode == 0, proc.stdout
    audit = read_report(project)["intent_audit"]
    assert audit["post_hoc_accepted"] is False
    assert audit["post_hoc_entries"] == []


def test_deleting_report_does_not_reset_post_hoc_window(project, run_rf, write):
    """The audit journal is redundancy: removing report.json must not clear a
    pending post-hoc entry (or the anti-rebaseline guard)."""
    setup_lib(project, run_rf, write)
    write(project / "samplelib" / "__init__.py", LIB_WITHOUT_RETRYPOLICY)
    run_rf(["check"], project, expect_exit=3)
    write_intent(project, write, [
        {"surface": "public_api", "target": "samplelib.RetryPolicy",
         "category": "symbol_removed", "note": "intentional removal"},
    ])
    run_rf(["check"], project, expect_exit=1)

    (project / ".regression-firewall" / "report.json").unlink()
    again = run_rf(["check"], project)
    assert again.returncode == 1, again.stdout  # still REVIEW via the journal
    audit = read_report(project)["intent_audit"]
    assert audit["post_hoc_pending"] is True
    assert audit["previous"]["source"] == "previous-check"
    assert audit["previous"]["verdict"] == "REVIEW"

    # The anti-rebaseline guard also consults the journal.
    (project / ".regression-firewall" / "report.json").unlink()
    rebaseline = run_rf(["baseline"], project)
    assert rebaseline.returncode != 0
    assert "Refusing to overwrite" in rebaseline.stdout
