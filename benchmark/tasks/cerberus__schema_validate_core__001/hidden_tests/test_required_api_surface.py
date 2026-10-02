"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Validator,
    DocumentError,
    SchemaError,
)


def test_required_api_surface():
    assert isinstance(Validator, type)
    assert Validator is not None
    assert Validator is not None
    assert hasattr(Validator, 'validate')
    assert issubclass(DocumentError, BaseException)
    assert issubclass(SchemaError, BaseException)
