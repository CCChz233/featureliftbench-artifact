"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Int,
    String,
    Dict,
    Key,
    Or,
    And,
    Forward,
    DataError,
)


def test_required_api_surface():
    assert isinstance(Int, type)
    assert isinstance(String, type)
    assert isinstance(Dict, type)
    assert hasattr(Dict, 'check')
    assert isinstance(Key, type)
    assert isinstance(Or, type)
    assert hasattr(Or, 'check')
    assert isinstance(And, type)
    assert hasattr(And, 'check')
    assert isinstance(Forward, type)
    assert hasattr(Forward, 'set_type')
    assert hasattr(Forward, 'check')
    assert issubclass(DataError, BaseException)
