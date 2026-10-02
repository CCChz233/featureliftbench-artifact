"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ConfigObj,
    DuplicateError,
    flatten_errors,
    get_extra_values,
    validate,
)


def test_required_api_surface():
    assert isinstance(ConfigObj, type)
    assert hasattr(ConfigObj, 'validate')
    assert hasattr(ConfigObj, 'write')
    assert hasattr(ConfigObj, '__getitem__')
    assert issubclass(DuplicateError, BaseException)
    assert callable(flatten_errors)
    assert callable(get_extra_values)
    assert validate is not None
    assert isinstance(getattr(validate, 'Validator'), type)
    assert issubclass(getattr(validate, 'VdtValueTooSmallError'), BaseException)
