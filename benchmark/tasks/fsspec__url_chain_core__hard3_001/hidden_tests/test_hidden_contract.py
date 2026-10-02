
import pytest

from featurelifted import ProtocolRegistry, UnknownProtocolError, url_to_fs


def test_chained_zip_file_url():
    registry = ProtocolRegistry()
    protocol, path, options = url_to_fs("zip://archive.zip::file:///tmp/archive.zip", registry)
    assert protocol == "zip"
    assert options["target_protocol"] == "file"


def test_storage_options_query():
    registry = ProtocolRegistry()
    protocol, path, options = url_to_fs("memory://data?storage_options=anon=true", registry)
    assert protocol == "memory"
    assert options["anon"] == "true"


def test_unknown_protocol_raises():
    registry = ProtocolRegistry()
    with pytest.raises(UnknownProtocolError):
        url_to_fs("unknown://data", registry)
