"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    BaseSettings,
    SettingsConfigDict,
    SettingsError,
)


def test_required_api_surface():
    assert isinstance(BaseSettings, type)
    assert isinstance(SettingsConfigDict, type)
    assert issubclass(SettingsError, BaseException)
