
from featurelifted import build_url


def test_build_url_appends_query():
    url = build_url("https://example.com/path", [("q", "a"), ("q", "b")])
    assert "q=a" in url and "q=b" in url
