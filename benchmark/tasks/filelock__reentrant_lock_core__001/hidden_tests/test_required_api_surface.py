"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    FileLock,
    Timeout,
)


def test_required_api_surface():
    assert isinstance(FileLock, type)
    assert hasattr(FileLock, 'acquire')
    assert FileLock is not None
    assert hasattr(FileLock, 'release')
    assert issubclass(Timeout, BaseException)
