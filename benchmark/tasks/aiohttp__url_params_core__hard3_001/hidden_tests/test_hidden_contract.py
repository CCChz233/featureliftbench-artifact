
import pytest

from featurelifted import CIMultiDict, InvalidHeaderName, build_url, normalize_headers


def test_build_url_preserves_existing_query():
    url = build_url("https://example.com/path?x=1", [("y", "2")])
    assert "x=1" in url and "y=2" in url


def test_ci_multidict_case_insensitive():
    headers = normalize_headers({"Content-Type": "text/plain", "content-length": "10"})
    assert headers["content-type"] == "text/plain"
    assert headers.getall("Content-Length") == ["10"]


def test_invalid_header_name_raises():
    headers = CIMultiDict()
    with pytest.raises(InvalidHeaderName):
        headers["bad header"] = "1"
