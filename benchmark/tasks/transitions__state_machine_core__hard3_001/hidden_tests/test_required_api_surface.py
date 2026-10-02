"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    MachineError,
    Machine,
)


def test_required_api_surface():
    assert issubclass(MachineError, BaseException)
    assert isinstance(Machine, type)
    assert hasattr(Machine, '__init__')
