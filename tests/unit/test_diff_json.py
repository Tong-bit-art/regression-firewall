from regression_firewall.diff.engine import diff_json, json_type
from regression_firewall.models.change import MISSING


def cats(entries):
    return {e["path"]: e["category"] for e in entries}


def test_no_changes():
    assert diff_json({"a": 1}, {"a": 1}) == []


def test_field_removed_and_added():
    entries = diff_json({"a": 1, "b": 2}, {"a": 1, "c": 3})
    by_cat = {e["category"]: e for e in entries}
    assert by_cat["field_removed"]["path"] == "$.b"
    assert by_cat["field_removed"]["before"] == 2
    assert by_cat["field_removed"]["after"] is MISSING
    assert by_cat["field_added"]["path"] == "$.c"
    assert by_cat["field_added"]["after"] == 3


def test_value_changed():
    entries = diff_json({"a": 1}, {"a": 2})
    assert cats(entries) == {"$.a": "value_changed"}


def test_field_type_changed():
    entries = diff_json({"age": 30}, {"age": "30"})
    assert cats(entries) == {"$.age": "field_type_changed"}


def test_bool_vs_number_is_type_change():
    assert cats(diff_json({"ok": True}, {"ok": 1})) == {"$.ok": "field_type_changed"}
    assert cats(diff_json({"ok": 1}, {"ok": True})) == {"$.ok": "field_type_changed"}


def test_int_and_float_equal_numbers():
    assert diff_json({"a": 1}, {"a": 1.0}) == []


def test_nested_paths():
    before = {"user": {"email": "a@b.c", "ids": [1, 2]}}
    after = {"user": {"email": "a@b.c", "ids": [1, 2, 3]}}
    entries = diff_json(before, after)
    assert cats(entries) == {"$.user.ids": "list_size_changed"}


def test_root_shape_change():
    entries = diff_json({"a": 1}, [1])
    assert cats(entries) == {"$": "response_shape_changed"}


def test_list_positional_recursion():
    before = {"items": [{"id": 1, "state": "new"}, {"id": 2}]}
    after = {"items": [{"id": 1, "state": "done"}, {"id": 2}]}
    entries = diff_json(before, after)
    assert cats(entries) == {"$.items[0].state": "value_changed"}


def test_null_to_number_is_type_change():
    # explicit JSON null is the "null" type; null -> number is a type change
    entries = diff_json({"a": None}, {"a": 5})
    assert cats(entries) == {"$.a": "field_type_changed"}


def test_json_types():
    assert json_type(None) == "null"
    assert json_type(True) == "boolean"
    assert json_type(1) == "number"
    assert json_type(1.5) == "number"
    assert json_type("x") == "string"
    assert json_type([]) == "array"
    assert json_type({}) == "object"
