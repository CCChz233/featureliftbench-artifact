"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Choices,
    Config,
    Csv,
    RepositoryDict,
    RepositoryEnv,
    UndefinedValueError,
)


def test_required_api_surface():
    assert isinstance(Choices, type)
    assert isinstance(Config, type)
    assert isinstance(Csv, type)
    assert isinstance(RepositoryDict, type)
    assert isinstance(RepositoryEnv, type)
    assert issubclass(UndefinedValueError, BaseException)
