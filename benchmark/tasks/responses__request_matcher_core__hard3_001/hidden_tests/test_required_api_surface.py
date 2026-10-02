"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    MockResponseRegistry,
    MockResponse,
    query_string_matcher,
    header_matcher,
)


def test_required_api_surface():
    assert isinstance(MockResponseRegistry, type)
    assert MockResponseRegistry is not None
    assert hasattr(MockResponseRegistry, 'add')
    assert MockResponseRegistry is not None
    assert hasattr(MockResponseRegistry, 'find')
    assert hasattr(MockResponseRegistry, 'reset')
    assert isinstance(MockResponse, type)
    assert callable(query_string_matcher)
    assert callable(header_matcher)
