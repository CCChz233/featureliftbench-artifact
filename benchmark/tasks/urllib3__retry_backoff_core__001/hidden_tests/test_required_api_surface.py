"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Retry,
    RequestHistory,
    ConnectTimeoutError,
    ReadTimeoutError,
    MaxRetryError,
    ResponseError,
    InvalidHeader,
)


def test_required_api_surface():
    assert isinstance(Retry, type)
    assert hasattr(Retry, 'get_backoff_time')
    assert Retry is not None
    assert hasattr(Retry, 'increment')
    assert hasattr(Retry, 'is_retry')
    assert hasattr(Retry, 'parse_retry_after')
    assert Retry is not None
    assert hasattr(Retry, 'from_int')
    assert Retry is not None
    assert isinstance(RequestHistory, type)
    assert issubclass(ConnectTimeoutError, BaseException)
    assert issubclass(ReadTimeoutError, BaseException)
    assert issubclass(MaxRetryError, BaseException)
    assert issubclass(ResponseError, BaseException)
    assert getattr(ResponseError, 'SPECIFIC_ERROR') is not None
    assert issubclass(InvalidHeader, BaseException)
