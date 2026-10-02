
from requests import PreparedRequest

from featurelifted import MockResponse, MockResponseRegistry, header_matcher, query_string_matcher


def test_query_and_header_matchers_and_once_behavior():
    registry = MockResponseRegistry()
    registry.add(
        MockResponse(
            url="http://example.com?a=1",
            method="GET",
            matchers=[query_string_matcher({"a": "1"}), header_matcher({"X-Test": "1"})],
            once=True,
        )
    )
    request = PreparedRequest()
    request.prepare(method="GET", url="http://example.com?a=1", headers={"X-Test": "1"})
    first, _ = registry.find(request)
    second, _ = registry.find(request)
    assert first is not None
    assert second is None
    assert len(registry.call_history) == 2


def test_reset_clears_registry_and_history():
    registry = MockResponseRegistry()
    registry.add(MockResponse(url="http://example.com"))
    registry.reset()
    assert registry._responses == []
    assert registry.call_history == []
