"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    PathAliases,
    exceptions,
)


def test_required_api_surface():
    assert isinstance(PathAliases, type)
    assert hasattr(PathAliases, 'map')
    assert hasattr(PathAliases, 'add')
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'ConfigError'), BaseException)
