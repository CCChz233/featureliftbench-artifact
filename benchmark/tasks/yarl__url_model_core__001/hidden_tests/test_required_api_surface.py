"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    URL,
    Query,
    QueryVariable,
    SimpleQuery,
    cache_clear,
    cache_configure,
    cache_info,
)


def test_required_api_surface():
    assert URL is not None
    assert Query is not None
    assert QueryVariable is not None
    assert SimpleQuery is not None
    assert callable(cache_clear)
    assert callable(cache_configure)
    assert callable(cache_info)
