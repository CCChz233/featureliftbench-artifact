"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    expand_factors,
    find_envs,
    filter_for_env,
)


def test_required_api_surface():
    assert callable(expand_factors)
    assert callable(find_envs)
    assert callable(filter_for_env)
