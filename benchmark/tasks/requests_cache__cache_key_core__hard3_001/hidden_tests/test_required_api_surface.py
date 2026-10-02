"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    CachePolicy,
    create_key,
    get_expiration,
    create_cache_key,
    normalize_body,
    normalize_headers,
    normalize_params,
)


def test_required_api_surface():
    assert isinstance(CachePolicy, type)
    assert hasattr(CachePolicy, 'from_headers')
    assert CachePolicy is not None
    assert CachePolicy is not None
    assert callable(create_key)
    assert callable(get_expiration)
    assert callable(create_cache_key)
    assert callable(normalize_body)
    assert callable(normalize_headers)
    assert callable(normalize_params)
