"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Env,
    EnvError,
    EnvValidationError,
    EnvSealedError,
    ParserConflictError,
    ValidationError,
    validate,
)


def test_required_api_surface():
    assert isinstance(Env, type)
    assert hasattr(Env, 'int')
    assert hasattr(Env, 'prefixed')
    assert hasattr(Env, 'seal')
    assert hasattr(Env, 'str')
    assert hasattr(Env, 'timedelta')
    assert issubclass(EnvError, BaseException)
    assert issubclass(EnvValidationError, BaseException)
    assert issubclass(EnvSealedError, BaseException)
    assert issubclass(ParserConflictError, BaseException)
    assert issubclass(ValidationError, BaseException)
    assert validate is not None
    assert isinstance(getattr(validate, 'Range'), type)
