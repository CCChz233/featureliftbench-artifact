"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    user_cache_dir,
    user_config_dir,
    user_data_dir,
)


def test_required_api_surface():
    assert callable(user_cache_dir)
    assert callable(user_config_dir)
    assert callable(user_data_dir)
