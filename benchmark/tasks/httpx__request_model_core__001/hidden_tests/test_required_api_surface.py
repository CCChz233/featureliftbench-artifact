"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    URL,
    QueryParams,
    Headers,
    Cookies,
    Request,
    build_request,
    InvalidURL,
)


def test_required_api_surface():
    assert URL is not None
    assert isinstance(QueryParams, type)
    assert hasattr(QueryParams, 'multi_items')
    assert hasattr(QueryParams, 'merge')
    assert isinstance(Headers, type)
    assert Headers is not None
    assert isinstance(Cookies, type)
    assert isinstance(Request, type)
    assert Request is not None
    assert Request is not None
    assert Request is not None
    assert callable(build_request)
    assert issubclass(InvalidURL, BaseException)
