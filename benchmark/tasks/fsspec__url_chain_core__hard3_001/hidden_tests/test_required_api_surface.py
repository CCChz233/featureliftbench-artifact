"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ProtocolRegistry,
    url_to_fs,
    UnknownProtocolError,
)


def test_required_api_surface():
    assert isinstance(ProtocolRegistry, type)
    assert callable(url_to_fs)
    assert issubclass(UnknownProtocolError, BaseException)
