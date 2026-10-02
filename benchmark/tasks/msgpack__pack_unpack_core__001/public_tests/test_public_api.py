from __future__ import annotations

from featurelifted import Packer, Unpacker, packb, unpackb


def _roundtrip(value, *, pack_kwargs=None, unpack_kwargs=None):
    pack_kwargs = pack_kwargs or {}
    unpack_kwargs = unpack_kwargs or {}
    return unpackb(packb(value, **pack_kwargs), **unpack_kwargs)


def test_pack_unpack_none_bool_int() -> None:
    assert _roundtrip(None) is None
    assert _roundtrip(True) is True
    assert _roundtrip(False) is False
    assert _roundtrip(42) == 42
    assert _roundtrip(-7) == -7


def test_pack_unpack_string_and_bytes() -> None:
    assert _roundtrip("hello") == "hello"
    packed = packb(b"abc", use_bin_type=True)
    assert unpackb(packed) == b"abc"


def test_pack_unpack_list_and_dict() -> None:
    assert _roundtrip([1, "two", None]) == [1, "two", None]
    assert _roundtrip({"a": 1, "b": [2, 3]}) == {"a": 1, "b": [2, 3]}


def test_packer_unpacker_streaming() -> None:
    data = packb({"x": [1, 2, 3]})
    unpacker = Unpacker()
    unpacker.feed(data)
    assert unpacker.unpack() == {"x": [1, 2, 3]}


def test_dumps_loads_aliases() -> None:
    from featurelifted import dumps, loads

    payload = dumps([1, 2, 3])
    assert loads(payload) == [1, 2, 3]
