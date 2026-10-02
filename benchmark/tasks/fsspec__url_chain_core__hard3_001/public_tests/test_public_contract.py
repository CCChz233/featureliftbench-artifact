
from featurelifted import ProtocolRegistry, url_to_fs


def test_simple_file_url():
    registry = ProtocolRegistry()
    protocol, path, options = url_to_fs("file:///tmp/data.txt", registry)
    assert protocol == "file"
    assert path == "/tmp/data.txt"
