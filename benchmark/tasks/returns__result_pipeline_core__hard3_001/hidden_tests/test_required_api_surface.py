"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Result,
    Success,
    Failure,
    safe,
)


def test_required_api_surface():
    assert isinstance(Result, type)
    assert isinstance(Success, type)
    assert hasattr(Success, 'map')
    assert Success is not None
    assert hasattr(Success, 'bind')
    assert isinstance(Failure, type)
    assert Failure is not None
    assert hasattr(Failure, 'map')
    assert hasattr(Failure, 'bind')
    assert callable(safe)
