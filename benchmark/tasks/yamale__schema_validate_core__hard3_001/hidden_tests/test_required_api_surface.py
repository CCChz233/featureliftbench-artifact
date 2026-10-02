"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    make_schema,
    validate,
    ValidationResult,
    YamaleError,
)


def test_required_api_surface():
    assert callable(make_schema)
    assert callable(validate)
    assert isinstance(ValidationResult, type)
    assert issubclass(YamaleError, BaseException)
