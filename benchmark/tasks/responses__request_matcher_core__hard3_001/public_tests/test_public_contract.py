
from requests import PreparedRequest

from featurelifted import MockResponse, MockResponseRegistry


def test_registry_finds_matching_response():
    registry = MockResponseRegistry()
    registry.add(MockResponse(url="http://example.com", method="GET", body="ok"))
    request = PreparedRequest()
    request.prepare(method="GET", url="http://example.com")
    response, reasons = registry.find(request)
    assert response is not None
    assert response.body == "ok"
