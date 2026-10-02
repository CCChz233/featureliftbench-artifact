"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse_fs_url,
    FSOpenerRegistry,
    ParseError,
    UnsupportedProtocolError,
    InvalidPathError,
    normalize_fs_path,
)


def test_required_api_surface():
    assert callable(parse_fs_url)
    assert isinstance(FSOpenerRegistry, type)
    assert hasattr(FSOpenerRegistry, 'open')
    assert hasattr(FSOpenerRegistry, 'register')
    assert issubclass(ParseError, BaseException)
    assert issubclass(UnsupportedProtocolError, BaseException)
    assert issubclass(InvalidPathError, BaseException)
    assert callable(normalize_fs_path)
