
import pytest

from featurelifted import (
    FSOpenerRegistry,
    InvalidPathError,
    ParseError,
    UnsupportedProtocolError,
    normalize_fs_path,
)


def test_default_protocol_injection():
    registry = FSOpenerRegistry(default_protocol="mem")

    @registry.register("mem")
    def open_mem(params):
        return object()

    fs, path = registry.open("/tmp/data")
    assert path is None


def test_unknown_protocol_raises():
    registry = FSOpenerRegistry()
    with pytest.raises(UnsupportedProtocolError):
        registry.open("missing://data")


def test_invalid_path_control_characters():
    with pytest.raises(InvalidPathError):
        normalize_fs_path("bad\x01path")
