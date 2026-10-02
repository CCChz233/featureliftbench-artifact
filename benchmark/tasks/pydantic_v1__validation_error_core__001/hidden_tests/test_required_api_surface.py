"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    BaseModel,
    Field,
    ValidationError,
    validator,
    root_validator,
    Extra,
)


def test_required_api_surface():
    assert isinstance(BaseModel, type)
    assert hasattr(BaseModel, 'parse_obj')
    assert callable(Field)
    assert issubclass(ValidationError, BaseException)
    assert callable(validator)
    assert callable(root_validator)
    assert isinstance(Extra, type)
    assert Extra.forbid is not None
