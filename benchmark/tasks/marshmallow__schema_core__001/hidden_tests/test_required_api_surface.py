"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Schema,
    fields,
    ValidationError,
    EXCLUDE,
    RAISE,
    decorators,
)


def test_required_api_surface():
    assert isinstance(Schema, type)
    assert hasattr(Schema, 'load')
    assert fields is not None
    assert isinstance(getattr(fields, 'Int'), type)
    assert isinstance(getattr(fields, 'List'), type)
    assert isinstance(getattr(fields, 'Nested'), type)
    assert isinstance(getattr(fields, 'Str'), type)
    assert issubclass(ValidationError, BaseException)
    assert EXCLUDE is not None
    assert RAISE is not None
    assert decorators is not None
    assert callable(getattr(decorators, 'post_load'))
    assert callable(getattr(decorators, 'validates_schema'))
