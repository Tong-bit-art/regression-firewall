import pytest

from regression_firewall.models.change import Change, MISSING
from regression_firewall.models.result import CheckResult
from regression_firewall.models.snapshot import ProbeCapture, Snapshot


def make_change(**kwargs):
    defaults = dict(surface="http", target="POST /login", category="status_changed",
                    before=401, after=400)
    defaults.update(kwargs)
    return Change(**defaults)


def test_change_id_stable_and_distinct():
    a = make_change()
    b = make_change()
    c = make_change(category="field_removed")
    assert a.change_id == b.change_id
    assert a.change_id != c.change_id
    assert len(a.change_id) == 12


def test_change_roundtrip():
    change = make_change(path="$.x", evidence={"transition": "error -> error"},
                         classification="unexpected", severity="high",
                         confidence=0.95, note=None)
    restored = Change.from_dict(change.to_dict())
    assert restored.surface == change.surface
    assert restored.category == change.category
    assert restored.before == change.before
    assert restored.after == change.after
    assert restored.severity == change.severity
    assert restored.change_id == change.change_id


def test_change_missing_side_serializes():
    change = make_change(category="field_added", before=MISSING, after=1)
    data = change.to_dict()
    assert data["before"] is None and data["before_present"] is False
    assert data["after"] == 1 and data["after_present"] is True


def test_snapshot_roundtrip():
    snapshot = Snapshot(
        schema_version="1", created_at="2026-10-04T00:00:00+00:00",
        tool_version="0.1.0", config_hash="abc",
        project={"name": "p", "language": "python", "frameworks": [], "package_name": None},
        surfaces={"cli": [ProbeCapture(probe_id="x", target="x", ok=True,
                                       data={"exit_code": 0})]},
    )
    restored = Snapshot.from_dict(snapshot.to_dict())
    assert restored.config_hash == "abc"
    assert restored.captures("cli")[0].data["exit_code"] == 0
    assert restored.probe_count() == 1


def test_snapshot_rejects_other_schema_version():
    with pytest.raises(ValueError, match="schema_version"):
        Snapshot.from_dict({"schema_version": "999"})


def test_check_result_summary_and_roundtrip():
    result = CheckResult(
        verdict="BLOCK", score=70, score_floored=True,
        changes=[make_change(classification="unexpected"),
                 make_change(classification="expected", category="field_added")],
        intent_source="none", warnings=["w1"], created_at="t", tool_version="0.1.0",
        project={"name": "p"},
    )
    assert result.summary == {"expected": 1, "unexpected": 1, "uncertain": 0}
    restored = CheckResult.from_dict(result.to_dict())
    assert restored.verdict == "BLOCK"
    assert restored.score == 70
    assert restored.summary == result.summary
    assert restored.warnings == ["w1"]
