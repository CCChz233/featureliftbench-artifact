"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    LazyCommandCollection,
    Command,
    UsageError,
)


def test_required_api_surface():
    assert isinstance(LazyCommandCollection, type)
    assert hasattr(LazyCommandCollection, 'get_command')
    assert hasattr(LazyCommandCollection, 'resolve')
    assert isinstance(Command, type)
    assert issubclass(UsageError, BaseException)
