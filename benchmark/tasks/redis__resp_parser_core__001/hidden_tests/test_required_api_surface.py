"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    _parsers,
    exceptions,
)


def test_required_api_surface():
    assert _parsers is not None
    assert isinstance(getattr(_parsers, 'Encoder'), type)
    assert hasattr(getattr(_parsers, 'Encoder'), 'encode')
    assert callable(getattr(_parsers, '_RESP2Parser'))
    assert callable(getattr(_parsers, '_RESP3Parser'))
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'ResponseError'), BaseException)
