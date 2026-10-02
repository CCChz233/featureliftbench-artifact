"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ActionRegistry,
    ConfigurationConflictError,
)


def test_required_api_surface():
    assert isinstance(ActionRegistry, type)
    assert hasattr(ActionRegistry, 'commit')
    assert hasattr(ActionRegistry, 'introspect')
    assert hasattr(ActionRegistry, 'register')
    assert issubclass(ConfigurationConflictError, BaseException)
