from __future__ import annotations

import re
from pathlib import Path

from featurelifted import URIBuilder, normalize_uri, uri_reference


def test_authority_userinfo_host_port() -> None:
    ref = uri_reference("https://User:Pass@Example.COM:8080/a")
    assert ref.userinfo == "User:Pass"
    assert ref.host == "Example.COM"
    assert ref.port == "8080"


def test_normalize_uri_path_dots() -> None:
    assert normalize_uri("HTTP://EXAMPLE.COM:80/a/../b") == "http://example.com:80/b"


def test_builder_from_uri_roundtrip() -> None:
    ref = uri_reference("https://example.com:443/a?x=1#top")
    rebuilt = URIBuilder.from_uri(ref).finalize()
    assert rebuilt.scheme == "https"
    assert rebuilt.host == "example.com"
    assert rebuilt.path == "/a"
    assert rebuilt.query == "x=1"
    assert rebuilt.fragment == "top"


def test_uri_reference_ipv6_host() -> None:
    ref = uri_reference("http://[::1]:8080/")
    assert ref.host == "[::1]"
    assert ref.port == "8080"


def test_normalize_preserves_fragment() -> None:
    assert normalize_uri("HTTPS://Example.COM/x#frag").endswith("#frag")


def test_no_rfc3986_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from rfc3986|import rfc3986)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))
