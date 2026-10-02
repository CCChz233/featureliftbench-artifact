"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    ProfileDoesNotExist,
    UnsupportedSettings,
    Settings,
    resolve_settings,
    resolve_from_path,
    find_config,
    should_skip,
)


def test_required_api_surface():
    assert issubclass(ProfileDoesNotExist, BaseException)
    assert issubclass(UnsupportedSettings, BaseException)
    assert isinstance(Settings, type)
    assert Settings is not None
    assert Settings is not None
    assert callable(resolve_settings)
    assert callable(resolve_from_path)
    assert callable(find_config)
    assert callable(should_skip)
    assert callable(getattr(Settings, 'is_skipped'))
