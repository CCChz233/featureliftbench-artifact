from __future__ import annotations

from featurelifted import URIBuilder, is_valid_uri, uri_reference


def test_uri_reference_components() -> None:
    ref = uri_reference("https://example.com:8080/path?q=1#frag")
    assert ref.scheme == "https"
    assert ref.host == "example.com"
    assert ref.port == "8080"
    assert ref.path == "/path"
    assert ref.query == "q=1"
    assert ref.fragment == "frag"


def test_is_valid_uri_https() -> None:
    assert is_valid_uri("https://example.com/path")


def test_uri_builder_finalize() -> None:
    built = URIBuilder().add_scheme("https").add_host("example.com").add_path("/x").finalize()
    assert built.scheme == "https"
    assert built.host == "example.com"
    assert built.path == "/x"
