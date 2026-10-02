"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    PluginManager,
    HookspecMarker,
    HookimplMarker,
    PluginValidationError,
)


def test_required_api_surface():
    assert isinstance(PluginManager, type)
    assert hasattr(PluginManager, 'check_pending')
    assert hasattr(PluginManager, 'add_hookspecs')
    assert PluginManager is not None
    assert hasattr(PluginManager, 'register')
    assert isinstance(HookspecMarker, type)
    assert isinstance(HookimplMarker, type)
    assert issubclass(PluginValidationError, BaseException)
