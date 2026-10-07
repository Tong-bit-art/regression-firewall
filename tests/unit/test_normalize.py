from regression_firewall.config.schema import (
    IgnoreConfig,
    NormalizationConfig,
)
from regression_firewall.normalize.engine import Normalizer

import pytest


@pytest.fixture
def norm():
    return Normalizer(NormalizationConfig(), IgnoreConfig())


# -- JSON value normalization -------------------------------------------------


def test_uuid_replaced(norm):
    assert norm.normalize_json("550e8400-e29b-41d4-a716-446655440000") == "<UUID>"


def test_uuid_inline_in_text(norm):
    assert norm.normalize_text("req 550e8400-e29b-41d4-a716-446655440000 done") == "req <UUID> done"


def test_uuid_off():
    n = Normalizer(NormalizationConfig(uuid=False), IgnoreConfig())
    assert n.normalize_json("550e8400-e29b-41d4-a716-446655440000") == "550e8400-e29b-41d4-a716-446655440000"


def test_iso_datetime_replaced(norm):
    assert norm.normalize_json("2026-10-04T22:41:00Z") == "<DATETIME>"
    assert norm.normalize_json("2026-10-04 22:41:00.123456+02:00") == "<DATETIME>"
    assert norm.normalize_json("2026-10-04") == "<DATETIME>"


def test_non_datetime_string_untouched(norm):
    assert norm.normalize_json("2026-10") == "2026-10"  # incomplete shape stays
    assert norm.normalize_json("v1.2.3") == "v1.2.3"


def test_epoch_with_temporal_key(norm):
    assert norm.normalize_json(1735689600, key="created_at") == "<TIMESTAMP>"
    assert norm.normalize_json(1735689600000, key="lastTimestamp") == "<TIMESTAMP>"
    assert norm.normalize_json("1735689600", key="updated_at") == "<TIMESTAMP>"


def test_epoch_without_key_hint_kept(norm):
    # business IDs are never masked even when they look like epochs
    assert norm.normalize_json(1735689600, key="order_no") == 1735689600
    assert norm.normalize_json(1735689600) == 1735689600


def test_epoch_out_of_range_kept(norm):
    assert norm.normalize_json(12345, key="created_at") == 12345
    assert norm.normalize_json(10**15, key="created_at") == 10**15


def test_request_id_key(norm):
    assert norm.normalize_json("abc-123", key="request_id") == "<REQUEST_ID>"
    assert norm.normalize_json("abc-123", key="x-request-id") == "<REQUEST_ID>"
    assert norm.normalize_json("abc-123", key="traceId") == "<REQUEST_ID>"


def test_token_key(norm):
    assert norm.normalize_json("hunter2", key="password") == "<TOKEN>"
    assert norm.normalize_json("Bearer x.y.z", key="Authorization") == "<TOKEN>"
    assert norm.normalize_json("sess-xyz", key="session") == "<TOKEN>"


def test_business_id_not_masked(norm):
    assert norm.normalize_json("abc-123", key="user_id") == "abc-123"
    assert norm.normalize_json(424242, key="id") == 424242


def test_duration_key(norm):
    assert norm.normalize_json(123.45, key="duration_ms") == "<DURATION>"
    assert norm.normalize_json(123.45, key="elapsed") == "<DURATION>"
    assert norm.normalize_json(123.45, key="size") == 123.45


def test_float_precision(norm):
    assert norm.normalize_json(0.30000000000000004) == 0.3
    assert norm.normalize_json(-0.0) == 0.0
    assert norm.normalize_json(True) is True  # booleans untouched


def test_temp_path(norm):
    assert norm.normalize_json("C:\\Users\\x\\AppData\\Local\\Temp\\out.txt") == "<TEMP_PATH>"
    assert norm.normalize_json("/tmp/build-cache/xyz") == "<TEMP_PATH>"
    assert norm.normalize_json("templates/index.html") == "templates/index.html"
    assert norm.normalize_json("src/utils/tempfile.py") == "src/utils/tempfile.py"


def test_nested_structures(norm):
    value = {
        "user": {
            "name": "alice",
            "created_at": 1735689600,
            "api_key": "secret",
        },
        "items": [{"id": 1, "ts": "2026-10-04T10:00:00Z"}],
        "version": 1.20000000004,
    }
    normalized = norm.normalize_json(value)
    assert normalized["user"]["created_at"] == "<TIMESTAMP>"
    assert normalized["user"]["api_key"] == "<TOKEN>"
    assert normalized["items"][0]["ts"] == "<DATETIME>"
    assert normalized["items"][0]["id"] == 1
    assert normalized["version"] == 1.2
    assert normalized["user"]["name"] == "alice"


# -- header / cookie normalization --------------------------------------------


def test_headers_ignored_and_normalized(norm):
    headers = {
        "Date": "Thu, 04 Oct 2026 22:41:00 GMT",
        "Content-Length": "42",
        "X-Request-Id": "550e8400-e29b-41d4-a716-446655440000",
        "Content-Type": "application/json",
    }
    out = norm.normalize_headers(headers)
    assert "date" not in out
    assert "content-length" not in out
    assert out["x-request-id"] == "<UUID>"
    assert out["content-type"] == "application/json"


def test_cookies_normalized_by_name(norm):
    out = norm.normalize_cookies({"session": "abc123", "theme": "dark"})
    assert out["session"] == "<TOKEN>"
    assert out["theme"] == "dark"


# -- text normalization --------------------------------------------------------


def test_text_line_endings_and_trailing_ws(norm):
    assert norm.normalize_text("a  \r\nb\t\r\n") == "a\nb\n"


def test_ansi_stripped(norm):
    assert norm.normalize_text("\x1b[31merror\x1b[0m: boom") == "error: boom"


def test_text_uuid_and_datetime_inlined(norm):
    text = norm.normalize_text("at 2026-10-04T10:00:00Z id 550e8400-e29b-41d4-a716-446655440000 ok")
    assert text == "at <DATETIME> id <UUID> ok"


# -- ignore paths ---------------------------------------------------------------


def test_json_path_ignore():
    n = Normalizer(NormalizationConfig(), IgnoreConfig(json_paths=["*.debug_trace"]))
    assert n.normalize_json("anything", key="debug_trace", path="user.debug_trace") == "anything"
    assert n.normalize_json("v", key="request_id", path="user.request_id") == "<REQUEST_ID>"


def test_json_path_ignore_nested():
    n = Normalizer(NormalizationConfig(), IgnoreConfig(json_paths=["items.0.seed"]))
    value = {"items": [{"seed": "abc", "name": "x"}]}
    out = n.normalize_json(value)
    assert out["items"][0]["seed"] == "abc"
    assert out["items"][0]["name"] == "x"


def test_cors_headers_order_insensitive():
    """Real-world finding: Django emits Access-Control-Allow-Methods in
    nondeterministic set order per process; the header is set-semantic and
    must not produce a diff."""
    n = Normalizer(NormalizationConfig(), IgnoreConfig())
    a = n.normalize_headers({"Access-Control-Allow-Methods": "POST, OPTIONS, GET"})
    b = n.normalize_headers({"Access-Control-Allow-Methods": "OPTIONS, POST, GET"})
    assert a == b
    assert a["access-control-allow-methods"] == "GET, OPTIONS, POST"
    # non-CORS headers keep their order
    keep = n.normalize_headers({"Vary": "Accept-Encoding, User-Agent"})
    assert keep["vary"] == "Accept-Encoding, User-Agent"


def test_float_epoch_string_with_temporal_key():
    """Real-world finding: str(time.time()) under a timestamp-ish key is a
    float string; it must normalize like integer epochs."""
    n = Normalizer(NormalizationConfig(), IgnoreConfig())
    assert n.normalize_json("1791257092.123456", key="x_benchmark_timestamp") == "<TIMESTAMP>"
    assert n.normalize_headers({"x-benchmark-timestamp": "1791257092.123"}) == \
        {"x-benchmark-timestamp": "<TIMESTAMP>"}
    # non-epoch floats stay untouched
    assert n.normalize_json("3.14", key="ratio") == "3.14"
