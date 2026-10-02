"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    loads,
    load,
)


def test_required_api_surface():
    assert callable(loads)
    assert callable(load)
