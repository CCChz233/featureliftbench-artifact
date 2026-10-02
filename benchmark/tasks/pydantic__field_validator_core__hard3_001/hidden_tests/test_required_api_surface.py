"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    field_validator,
    BaseModel,
    ValidationError,
)


def test_required_api_surface():
    assert callable(field_validator)
    assert isinstance(BaseModel, type)
    assert issubclass(ValidationError, BaseException)
