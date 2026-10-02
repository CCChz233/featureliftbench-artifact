"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Signal,
)


def test_required_api_surface():
    assert isinstance(Signal, type)
    assert hasattr(Signal, 'connect')
    assert hasattr(Signal, 'send')
