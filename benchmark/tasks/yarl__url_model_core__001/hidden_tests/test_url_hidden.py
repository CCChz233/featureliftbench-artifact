from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

import pytest
from multidict import MultiDict

from featurelifted import URL


def test_duplicate_query_keys_multidict() -> None:
    url = URL("http://example.com/?a=1&a=2&b=3")
    assert url.query.getall("a") == ["1", "2"]
    assert list(url.query.items()) == [("a", "1"), ("a", "2"), ("b", "3")]


def test_semicolon_in_query_value_not_separator() -> None:
    url = URL("http://127.0.0.1/?a=10;b=20")
    assert len(url.query) == 1
    assert url.query["a"] == "10;b=20"


def test_idna_unicode_host_decoded() -> None:
    url = URL("http://xn--nxasmq5b.com/")
    assert url.host == "όβλοσ.com"
    assert "xn--" not in url.human_repr()


def test_join_relative_parent_path() -> None:
    base = URL("http://example.com/a/b/c")
    joined = base.join(URL("../d"))
    assert joined.path == "/a/d"


def test_joinpath_normalizes_dot_segments() -> None:
    url = URL("http://example.com/").joinpath("foo", ".", "bar", "..", "baz")
    assert url.path == "/foo/baz"


def test_default_http_port_omitted_from_str() -> None:
    assert str(URL("http://example.com:80/")) == "http://example.com/"


def test_query_no_double_unquote() -> None:
    sample_url = "http://base.place?" + urlencode({"a": "/////"})
    query = urlencode({"url": sample_url})
    full_url = "http://test_url.aha?" + query
    url = URL(full_url)
    assert url.query["url"] == sample_url


def test_update_query_with_multidict() -> None:
    base = URL("http://example.com/?a=1")
    updated = base.update_query(MultiDict([("b", "2"), ("a", "9")]))
    assert updated.query.getall("a") == ["9"]
    assert updated.query["b"] == "2"
    assert base.query["a"] == "1"


def test_join_preserves_base_query_when_relative_has_query_only() -> None:
    base = URL("http://example.com/path?keep=1")
    joined = base.join(URL("?only=2"))
    assert joined.query["only"] == "2"
    assert "keep" not in joined.query


def test_no_yarl_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from yarl|import yarl)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))


def test_join_rejects_non_url_type() -> None:
    with pytest.raises(TypeError, match="url should be URL"):
        URL("http://example.com/").join("relative")  # type: ignore[arg-type]
