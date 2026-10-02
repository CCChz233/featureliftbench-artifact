"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    SourceSelector,
)


def test_required_api_surface():
    assert isinstance(SourceSelector, type)
    assert hasattr(SourceSelector, 'skip_reason')
