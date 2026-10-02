"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    version_from_scm,
)


def test_required_api_surface():
    assert callable(version_from_scm)
