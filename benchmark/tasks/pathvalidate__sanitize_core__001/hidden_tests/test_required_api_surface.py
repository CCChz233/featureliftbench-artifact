"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Platform,
    sanitize_filename,
    sanitize_filepath,
    validate_filename,
    validate_filepath,
    is_valid_filename,
    is_valid_filepath,
    ValidationError,
    ErrorReason,
    ReservedNameError,
    InvalidCharError,
)


def test_required_api_surface():
    assert isinstance(Platform, type)
    assert callable(sanitize_filename)
    assert callable(sanitize_filepath)
    assert callable(validate_filename)
    assert callable(validate_filepath)
    assert callable(is_valid_filename)
    assert callable(is_valid_filepath)
    assert issubclass(ValidationError, BaseException)
    assert isinstance(ErrorReason, type)
    assert ErrorReason is not None
    assert ErrorReason is not None
    assert issubclass(ReservedNameError, BaseException)
    assert issubclass(InvalidCharError, BaseException)
