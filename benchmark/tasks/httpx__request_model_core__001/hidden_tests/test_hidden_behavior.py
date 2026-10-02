from __future__ import annotations

from pathlib import Path
import re

import pytest

from featurelifted import Cookies, Headers, InvalidURL, QueryParams, Request, URL, build_request


def test_base_url_join_and_duplicate_query_params() -> None:
    request = build_request(
        "GET",
        "/path?extra=1",
        base_url="https://example.com/api/",
        default_params={"limit": "10"},
        params={"offset": "0"},
    )
    assert str(request.url).startswith("https://example.com/api/path")
    pairs = list(request.url.params.multi_items())
    assert ("extra", "1") in pairs
    assert ("limit", "10") in pairs
    assert ("offset", "0") in pairs

    duplicate = QueryParams([("a", "1"), ("a", "2")])
    assert list(duplicate.multi_items()) == [("a", "1"), ("a", "2")]


def test_headers_cookie_merge_and_request_object() -> None:
    repeated = Headers([("X-Trace", "1"), ("X-Trace", "2")])
    assert len(repeated.raw) == 2

    request = build_request(
        "POST",
        "https://example.com/submit",
        default_headers=[("X-Trace", "1"), ("X-Trace", "2")],
        headers=[("x-trace", "3"), ("Content-Type", "text/plain")],
        default_cookies={"a": "1"},
        cookies={"b": "2"},
        content=b"payload",
    )
    assert request.headers["x-trace"] == "3"
    assert request.headers["content-type"] == "text/plain"
    cookie_header = request.headers.get("cookie", "")
    assert "a=1" in cookie_header
    assert "b=2" in cookie_header
    assert request.content == b"payload"


def test_build_request_merges_client_defaults() -> None:
    request = build_request(
        "PUT",
        "https://example.com/resource",
        default_headers={"Authorization": "Bearer base"},
        headers={"Authorization": "Bearer override"},
        default_params={"keep": "yes"},
        params={"q": "new"},
        default_cookies={"sid": "base"},
        cookies={"sid": "override", "pref": "dark"},
    )
    assert request.headers["Authorization"] == "Bearer override"
    assert list(request.url.params.multi_items()) == [("keep", "yes"), ("q", "new")]
    cookie_header = request.headers.get("cookie", "")
    assert "sid=override" in cookie_header
    assert "pref=dark" in cookie_header


def test_request_content_data_json_headers() -> None:
    json_request = build_request("POST", "https://example.com/json", json={"x": 1})
    assert json_request.headers["content-type"].startswith("application/json")
    assert b'"x": 1' in json_request.content

    data_request = build_request(
        "POST",
        "https://example.com/form",
        data={"a": "b"},
    )
    assert "application/x-www-form-urlencoded" in data_request.headers["content-type"]
    assert b"a=b" in data_request.content

    content_request = build_request(
        "POST",
        "https://example.com/raw",
        content=b"bytes",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert content_request.content == b"bytes"
    assert content_request.headers["content-type"] == "application/octet-stream"


def test_url_idna_and_percent_encoding() -> None:
    url = URL("http://中国.icom.museum/pa%20th")
    assert url.host == "中国.icom.museum"
    assert url.raw_host == b"xn--fiqs8s.icom.museum"
    assert url.path == "/pa th"

    joined = build_request(
        "GET",
        "../search",
        base_url="https://example.com/api/v1/items/",
    )
    assert str(joined.url) == "https://example.com/api/v1/search"


def test_query_params_duplicate_and_empty_value() -> None:
    params = QueryParams([("a", ""), ("a", "2"), ("b", "1")])
    assert list(params.multi_items()) == [("a", ""), ("a", "2"), ("b", "1")]
    merged = QueryParams([("a", "1")]).merge([("a", "2"), ("c", "3")])
    assert list(merged.multi_items()) == [("a", "2"), ("c", "3")]


def test_invalid_url_raises() -> None:
    with pytest.raises(InvalidURL):
        URL("http://\n")


def test_no_network_api_surface() -> None:
    import featurelifted

    forbidden = {
        "Client",
        "AsyncClient",
        "HTTPTransport",
        "AsyncHTTPTransport",
        "send",
        "stream",
        "get",
        "post",
    }
    for name in forbidden:
        assert not hasattr(featurelifted, name), f"unexpected network API: {name}"

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from httpx|import httpx)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
