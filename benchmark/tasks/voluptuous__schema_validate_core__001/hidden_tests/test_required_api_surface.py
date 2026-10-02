"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Schema,
    Required,
    Optional,
    All,
    Any,
    In,
    Coerce,
    Invalid,
    MultipleInvalid,
    SchemaError,
)


def test_required_api_surface():
    assert isinstance(Schema, type)
    assert isinstance(Required, type)
    assert isinstance(Optional, type)
    assert isinstance(All, type)
    assert isinstance(Any, type)
    assert isinstance(In, type)
    assert isinstance(Coerce, type)
    assert issubclass(Invalid, BaseException)
    assert issubclass(MultipleInvalid, BaseException)
    assert issubclass(SchemaError, BaseException)
