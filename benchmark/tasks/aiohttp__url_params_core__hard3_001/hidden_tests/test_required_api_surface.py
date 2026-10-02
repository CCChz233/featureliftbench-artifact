"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    build_url,
    normalize_headers,
    CIMultiDict,
    InvalidHeaderName,
)


def test_required_api_surface():
    assert callable(build_url)
    assert callable(normalize_headers)
    assert isinstance(CIMultiDict, type)
    assert hasattr(CIMultiDict, 'getall')
    assert hasattr(CIMultiDict, '__getitem__')
    assert hasattr(CIMultiDict, '__setitem__')
    assert issubclass(InvalidHeaderName, BaseException)
