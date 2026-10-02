"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    packb,
    unpackb,
    pack,
    unpack,
    dumps,
    loads,
    Packer,
    Unpacker,
    ExtType,
    Timestamp,
    ExtraData,
    FormatError,
)


def test_required_api_surface():
    assert callable(packb)
    assert callable(unpackb)
    assert callable(pack)
    assert callable(unpack)
    assert callable(dumps)
    assert callable(loads)
    assert isinstance(Packer, type)
    assert isinstance(Unpacker, type)
    assert isinstance(ExtType, type)
    assert isinstance(Timestamp, type)
    assert issubclass(ExtraData, BaseException)
    assert issubclass(FormatError, BaseException)
