from __future__ import annotations

from featurelifted import URL


def test_basic_parse_components() -> None:
    url = URL("http://example.com:8080/foo?bar=1#frag")
    assert url.scheme == "http"
    assert url.host == "example.com"
    assert url.port == 8080
    assert url.path == "/foo"
    assert url.fragment == "frag"
    assert url.query["bar"] == "1"


def test_join_absolute_path() -> None:
    base = URL("http://example.com/a/b")
    joined = base.join(URL("/c"))
    assert str(joined) == "http://example.com/c"


def test_with_query_kwargs() -> None:
    url = URL("http://example.com/").with_query(a=1, b=2)
    assert url.query["a"] == "1"
    assert url.query["b"] == "2"


def test_joinpath_appends_segments() -> None:
    url = URL("http://example.com/base").joinpath("child", "leaf")
    assert url.path == "/base/child/leaf"
