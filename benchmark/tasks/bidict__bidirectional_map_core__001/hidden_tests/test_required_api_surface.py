"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    bidict,
    frozenbidict,
    OrderedBidict,
    ON_DUP_RAISE,
    ValueDuplicationError,
    KeyAndValueDuplicationError,
    inverted,
)


def test_required_api_surface():
    assert callable(bidict)
    assert callable(frozenbidict)
    assert isinstance(OrderedBidict, type)
    assert hasattr(OrderedBidict, 'keys')
    assert hasattr(OrderedBidict, 'move_to_end')
    assert ON_DUP_RAISE is not None
    assert issubclass(ValueDuplicationError, BaseException)
    assert issubclass(KeyAndValueDuplicationError, BaseException)
    assert callable(inverted)
