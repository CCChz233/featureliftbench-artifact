"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Schema,
    Optional,
    Or,
    And,
    SchemaError,
)


def test_required_api_surface():
    assert isinstance(Schema, type)
    assert hasattr(Schema, 'validate')
    assert isinstance(Optional, type)
    assert isinstance(Or, type)
    assert hasattr(Or, 'validate')
    assert isinstance(And, type)
    assert hasattr(And, 'validate')
    assert issubclass(SchemaError, BaseException)
