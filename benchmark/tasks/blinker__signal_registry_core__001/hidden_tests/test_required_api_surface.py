"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ANY,
    Namespace,
    Signal,
)


def test_required_api_surface():
    assert ANY is not None
    assert isinstance(Namespace, type)
    assert isinstance(Signal, type)
    assert hasattr(Signal, 'connect')
    assert hasattr(Signal, 'send')
