"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    HookCaller,
)


def test_required_api_surface():
    assert isinstance(HookCaller, type)
    assert hasattr(HookCaller, 'add_hookimpl')
    assert hasattr(HookCaller, 'call_extra')
    assert hasattr(HookCaller, 'get_hookimpls')
