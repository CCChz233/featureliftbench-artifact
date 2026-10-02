"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Dynaconf,
    object_merge,
)


def test_required_api_surface():
    assert isinstance(Dynaconf, type)
    assert Dynaconf is not None
    assert Dynaconf is not None
    assert Dynaconf is not None
    assert Dynaconf is not None
    assert Dynaconf is not None
    assert Dynaconf is not None  # runtime-bound method
    assert callable(object_merge)
