"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    listen,
    remove,
    dispatch,
    EventTarget,
)


def test_required_api_surface():
    assert callable(listen)
    assert callable(remove)
    assert callable(dispatch)
    assert isinstance(EventTarget, type)
