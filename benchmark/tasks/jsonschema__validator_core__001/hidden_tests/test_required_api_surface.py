"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Draft202012Validator,
    validate,
    ValidationError,
    SchemaError,
    FormatChecker,
)


def test_required_api_surface():
    assert isinstance(Draft202012Validator, type)
    assert hasattr(Draft202012Validator, 'check_schema')
    assert hasattr(Draft202012Validator, 'is_valid')
    assert hasattr(Draft202012Validator, 'iter_errors')
    assert callable(validate)
    assert issubclass(ValidationError, BaseException)
    assert issubclass(SchemaError, BaseException)
    assert isinstance(FormatChecker, type)
