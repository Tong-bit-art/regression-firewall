from regression_firewall.intent.matcher import classify_change
from regression_firewall.intent.model import Intent, intent_from_dict
from regression_firewall.models.change import Change, MISSING


def make_change(category="status_changed", target="POST /login", surface="http",
                path=None, before=401, after=400):
    return Change(surface=surface, target=target, category=category, path=path,
                  before=before, after=after)


def test_no_intent_unexpected():
    classification, note = classify_change(make_change(), Intent(source="none"))
    assert classification == "unexpected"
    assert note is None


def test_exact_match_expected():
    intent = intent_from_dict({
        "task": "lockout",
        "expected_changes": [{"surface": "http", "target": "POST /login",
                              "category": "status_changed", "before": 401, "after": 423}],
    })
    change = make_change(before=401, after=423)
    classification, note = classify_change(change, intent)
    assert classification == "expected"


def test_value_constraint_mismatch_falls_through():
    intent = intent_from_dict({
        "expected_changes": [{"surface": "http", "target": "POST /login",
                              "category": "status_changed", "before": 401, "after": 423}],
    })
    classification, _ = classify_change(make_change(before=401, after=400), intent)
    assert classification == "unexpected"


def test_wildcard_category():
    intent = intent_from_dict({
        "expected_changes": [{"surface": "http", "target": "GET /users/*",
                              "category": "*", "note": "users endpoints reworked"}],
    })
    change = make_change(category="field_removed", target="GET /users/42", path="$.email")
    classification, note = classify_change(change, intent)
    assert classification == "expected"
    assert note == "users endpoints reworked"


def test_path_constraint():
    intent = intent_from_dict({
        "expected_changes": [{"surface": "http", "target": "GET /users/42",
                              "category": "field_removed", "path": "username"}],
    })
    matched = make_change(category="field_removed", target="GET /users/42", path="username")
    other = make_change(category="field_removed", target="GET /users/42", path="email")
    assert classify_change(matched, intent)[0] == "expected"
    assert classify_change(other, intent)[0] == "unexpected"


def test_uncertain_categories():
    for category in ("stdout_changed", "stderr_changed", "header_changed",
                     "field_added", "symbol_added", "file_created", "file_modified",
                     "value_changed", "list_size_changed"):
        assert classify_change(make_change(category=category), Intent()) == ("uncertain", None)


def test_structural_categories_unexpected():
    for category in ("status_changed", "exit_code_changed", "field_removed",
                     "field_type_changed", "symbol_removed", "signature_changed",
                     "file_deleted", "content_type_changed", "capture_error"):
        assert classify_change(make_change(category=category), Intent())[0] == "unexpected"


def test_missing_side_never_matches_constraint():
    # expectation with before: 401 must not match a change where before was absent
    intent = intent_from_dict({
        "expected_changes": [{"category": "symbol_added", "before": "x"}],
    })
    change = make_change(category="symbol_added", before=MISSING, after={"kind": "function"})
    assert classify_change(change, intent)[0] == "uncertain"


def test_rename_flow_expected():
    intent = intent_from_dict({
        "task": "rename username to display_name",
        "expected_changes": [
            {"surface": "http", "target": "GET /users/1", "category": "field_removed", "path": "username"},
            {"surface": "http", "target": "GET /users/1", "category": "field_added", "path": "display_name"},
        ],
    })
    removed = make_change(category="field_removed", target="GET /users/1", path="username")
    added = make_change(category="field_added", target="GET /users/1", path="display_name")
    assert classify_change(removed, intent)[0] == "expected"
    assert classify_change(added, intent)[0] == "expected"


def test_surface_mismatch():
    intent = intent_from_dict({
        "expected_changes": [{"surface": "cli", "target": "deploy", "category": "exit_code_changed"}],
    })
    change = make_change(category="exit_code_changed", target="deploy", surface="cli")
    other = make_change(category="exit_code_changed", target="deploy", surface="http")
    assert classify_change(change, intent)[0] == "expected"
    assert classify_change(other, intent)[0] == "unexpected"


def test_intent_path_bracket_indices_normalized():
    """Real-world finding: change paths use bracket array indexing
    ($.checks[0].desc) while intent files use dotted segments — the matcher
    must treat [0] as a path segment so globs like checks.*.desc match."""
    intent = intent_from_dict({
        "expected_changes": [{"surface": "http", "target": "GET /api/v1/checks/",
                              "category": "field_removed", "path": "checks.*.desc"}],
    })
    change = make_change(category="field_removed", target="GET /api/v1/checks/",
                         path="$.checks[0].desc")
    assert classify_change(change, intent)[0] == "expected"
