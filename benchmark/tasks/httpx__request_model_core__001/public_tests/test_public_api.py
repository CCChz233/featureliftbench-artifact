from __future__ import annotations

from featurelifted import Cookies, Headers, QueryParams, Request, URL, build_request


def test_url_path_and_query() -> None:
    url = URL("https://example.com/api/items?search=ab")
    assert url.scheme == "https"
    assert url.host == "example.com"
    assert url.path == "/api/items"
    assert url.query == b"search=ab"


def test_query_params_from_mapping() -> None:
    params = QueryParams({"a": "1", "b": "2"})
    assert list(params.multi_items()) == [("a", "1"), ("b", "2")]
    assert str(params) == "a=1&b=2"


def test_headers_case_insensitive_lookup() -> None:
    headers = Headers({"X-Token": "abc"})
    assert headers["x-token"] == "abc"
    headers["X-Token"] = "def"
    assert headers["X-TOKEN"] == "def"


def test_cookies_simple_header() -> None:
    cookies = Cookies({"session": "abc123"})
    request = Request("GET", "https://example.com/", cookies=cookies)
    assert "session=abc123" in request.headers.get("cookie", "")


def test_build_request_merges_defaults() -> None:
    request = build_request(
        "GET",
        "/items",
        base_url="https://api.example.com/v1/",
        default_headers={"X-Api-Key": "secret"},
        headers={"Accept": "application/json"},
        default_params={"limit": "10"},
        params={"offset": "0"},
    )
    assert str(request.url) == "https://api.example.com/v1/items?limit=10&offset=0"
    assert request.headers["X-Api-Key"] == "secret"
    assert request.headers["Accept"] == "application/json"
