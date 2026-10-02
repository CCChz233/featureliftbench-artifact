"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    decorate,
    decorator,
)


def test_required_api_surface():
    assert callable(decorate)
    assert callable(decorator)
