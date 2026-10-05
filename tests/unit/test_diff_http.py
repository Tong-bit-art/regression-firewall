from _helpers import change_of

from regression_firewall.diff.engine import make_change
from regression_firewall.diff.http import diff_http
from regression_firewall.models.snapshot import ProbeCapture


def capture(probe_id, data, ok=True, error=None):
    return ProbeCapture(probe_id=probe_id, target=probe_id, ok=ok, error=error, data=data)


def http_data(status, headers=None, cookies=None, body=None, body_kind="json"):
    return {"status": status, "headers": headers or {}, "cookies": cookies or {},
            "body": body, "body_kind": body_kind}



def test_status_change_401_to_400_is_high(cfg, norm):
    before = capture("POST /login", http_data(401, body={"error": "invalid"}))
    after = capture("POST /login", http_data(400, body={"error": "invalid"}))
    changes = diff_http(before, after, norm, cfg, make_change)
    change = change_of(changes, "status_changed")
    assert change.severity == "high"
    assert change.before == 401 and change.after == 400


def test_error_to_success_is_high(cfg, norm):
    before = capture("GET /x", http_data(500, body={}))
    after = capture("GET /x", http_data(200, body={}))
    changes = diff_http(before, after, norm, cfg, make_change)
    assert change_of(changes, "status_changed").severity == "high"


def test_success_to_success_is_medium(cfg, norm):
    before = capture("POST /things", http_data(200, body={"id": 1}))
    after = capture("POST /things", http_data(201, body={"id": 1}))
    changes = diff_http(before, after, norm, cfg, make_change)
    assert change_of(changes, "status_changed").severity == "medium"


def test_field_removed_is_high(cfg, norm):
    before = capture("GET /me", http_data(200, body={"id": 1, "email": "x@y.z"}))
    after = capture("GET /me", http_data(200, body={"id": 1}))
    changes = diff_http(before, after, norm, cfg, make_change)
    change = change_of(changes, "field_removed")
    assert change.severity == "high"
    assert change.path == "$.email"


def test_field_added_is_low(cfg, norm):
    before = capture("GET /me", http_data(200, body={"id": 1}))
    after = capture("GET /me", http_data(200, body={"id": 1, "debug": True}))
    changes = diff_http(before, after, norm, cfg, make_change)
    assert change_of(changes, "field_added").severity == "low"


def test_field_type_changed_is_medium(cfg, norm):
    before = capture("GET /me", http_data(200, body={"age": 30}))
    after = capture("GET /me", http_data(200, body={"age": "30"}))
    changes = diff_http(before, after, norm, cfg, make_change)
    assert change_of(changes, "field_type_changed").severity == "medium"


def test_content_type_change(cfg, norm):
    before = capture("GET /x", http_data(200, headers={"content-type": "application/json"}, body={"a": 1}))
    after = capture("GET /x", http_data(200, headers={"content-type": "text/plain"},
                                        body="{'a': 1}", body_kind="text"))
    changes = diff_http(before, after, norm, cfg, make_change)
    assert change_of(changes, "content_type_changed")
    # the body-kind flip is explained by the content-type change: no duplicate
    assert not [c for c in changes if c.category == "response_shape_changed"]


def test_header_change_detected_and_ignored_headers_skipped(cfg, norm):
    before = capture("GET /x", http_data(200, headers={"cache-control": "no-cache", "date": "today"}))
    after = capture("GET /x", http_data(200, headers={"cache-control": "max-age=60", "date": "tomorrow"}))
    changes = diff_http(before, after, norm, cfg, make_change)
    change = change_of(changes, "header_changed", path="cache-control")
    assert change.before == "no-cache" and change.after == "max-age=60"
    assert not [c for c in changes if c.path == "date"]


def test_cookie_change(cfg, norm):
    before = capture("GET /x", http_data(200, cookies={"consent": "v1"}))
    after = capture("GET /x", http_data(200, cookies={"consent": "v2"}))
    changes = diff_http(before, after, norm, cfg, make_change)
    assert change_of(changes, "cookie_changed", path="consent")


def test_session_cookie_value_masked_on_both_sides(cfg, norm):
    # session cookies are per-run volatile: both sides normalize to <TOKEN>,
    # so a value change must not become a false positive
    before = capture("GET /x", http_data(200, cookies={"session": "aaa"}))
    after = capture("GET /x", http_data(200, cookies={"session": "bbb"}))
    assert diff_http(before, after, norm, cfg, make_change) == []


def test_capture_error_flip(cfg, norm):
    before = capture("GET /x", {}, ok=False, error="ConnectionError: refused")
    after = capture("GET /x", http_data(200, body={}))
    changes = diff_http(before, after, norm, cfg, make_change)
    assert change_of(changes, "capture_error").severity == "high"


def test_timestamp_noise_normalized_away(cfg, norm):
    before = capture("GET /now", http_data(200, body={"timestamp": 1735689600, "v": 1}))
    after = capture("GET /now", http_data(200, body={"timestamp": 1735689601, "v": 1}))
    assert diff_http(before, after, norm, cfg, make_change) == []


def test_request_id_header_normalized_away(cfg, norm):
    before = capture("GET /x", http_data(200, headers={"x-request-id": "aaa"}))
    after = capture("GET /x", http_data(200, headers={"x-request-id": "bbb"}))
    assert diff_http(before, after, norm, cfg, make_change) == []
