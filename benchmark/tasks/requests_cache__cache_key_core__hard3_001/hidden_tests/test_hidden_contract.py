import json
from datetime import datetime, timezone

from featurelifted import CachePolicy, create_key, get_expiration, normalize_body, normalize_headers, normalize_params


def test_json_body_sorting_and_redaction_affect_cache_key():
    headers = {"Content-Type": "application/json"}
    first = create_key(
        "POST",
        "https://example.test/search",
        headers=headers,
        body='{"token":"abc","z":2,"a":1}',
        ignored_parameters=["token"],
    )
    second = create_key(
        "POST",
        "https://example.test/search",
        headers=headers,
        body='{"a":1,"z":2,"token":"def"}',
        ignored_parameters=["token"],
    )

    assert first == second
    assert json.loads(normalize_body('{"b":2,"a":1}', headers=headers)) == {"a": 1, "b": 2}


def test_form_body_and_key_only_params_are_normalized():
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    assert normalize_params("b=2&a=1&flag") == "a=1&b=2&flag"
    assert normalize_body("token=secret&b=2&a=1", headers=headers, ignored_parameters=["token"]) == (
        b"a=1&b=2&token=REDACTED"
    )


def test_match_headers_controls_key_variation():
    base = {"Accept": "application/json", "X-Trace": "one"}
    changed_trace = {"Accept": "application/json", "X-Trace": "two"}
    changed_accept = {"Accept": "text/plain", "X-Trace": "one"}

    assert create_key("GET", "https://example.test", headers=base) == create_key(
        "GET", "https://example.test", headers=changed_accept
    )
    assert create_key("GET", "https://example.test", headers=base, match_headers=["Accept"]) == create_key(
        "GET", "https://example.test", headers=changed_trace, match_headers=["Accept"]
    )
    assert create_key("GET", "https://example.test", headers=base, match_headers=["Accept"]) != create_key(
        "GET", "https://example.test", headers=changed_accept, match_headers=["Accept"]
    )


def test_header_multi_value_normalization_and_redaction():
    headers = normalize_headers({"Accept": "text/html, application/json", "Authorization": "secret"}, ["authorization"])

    assert headers["accept"] == "application/json, text/html"
    assert headers["authorization"] == "REDACTED"


def test_expires_header_and_default_expiration():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert get_expiration({"Expires": "Thu, 01 Jan 2026 00:01:30 GMT"}, now=now) == 90
    assert CachePolicy.from_headers({}, default=120).expiration_seconds == 120
