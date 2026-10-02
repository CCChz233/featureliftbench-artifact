"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Arrow,
    get,
)


def test_required_api_surface():
    assert isinstance(Arrow, type)
    assert Arrow is not None
    assert hasattr(Arrow, 'format')
    assert hasattr(Arrow, 'humanize')
    assert Arrow is not None
    assert Arrow is not None
    assert callable(get)
