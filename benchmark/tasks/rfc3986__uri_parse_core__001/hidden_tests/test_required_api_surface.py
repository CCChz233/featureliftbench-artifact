"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    URIBuilder,
    URIReference,
    is_valid_uri,
    normalize_uri,
    uri_reference,
)


def test_required_api_surface():
    assert isinstance(URIBuilder, type)
    assert hasattr(URIBuilder, 'from_uri')
    assert hasattr(URIBuilder, 'add_scheme')
    assert hasattr(URIBuilder, 'add_host')
    assert hasattr(URIBuilder, 'add_path')
    assert hasattr(URIBuilder, 'finalize')
    assert isinstance(URIReference, type)
    assert callable(is_valid_uri)
    assert callable(normalize_uri)
    assert callable(uri_reference)
