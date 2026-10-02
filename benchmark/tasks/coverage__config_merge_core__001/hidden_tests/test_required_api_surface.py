"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    CoverageConfig,
    read_run_config,
)


def test_required_api_surface():
    assert isinstance(CoverageConfig, type)
    assert callable(read_run_config)
