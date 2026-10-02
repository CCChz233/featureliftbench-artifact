from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import pytest

from featurelifted import (
    ExtType,
    ExtraData,
    FormatError,
    Packer,
    Timestamp,
    Unpacker,
    packb,
    unpackb,
)


def test_timestamp_roundtrip() -> None:
    ts = Timestamp(2**32 - 1)
    assert unpackb(packb(ts)) == ts
    ts64 = Timestamp(2**34 - 1, 999999999)
    assert unpackb(packb(ts64)) == ts64


def test_ext_type_roundtrip() -> None:
    ext = ExtType(1, b"payload")
    assert unpackb(packb(ext)) == ext


def test_strict_map_key_allows_int_keys() -> None:
    value = {1: "one", 2: "two"}
    packed = packb(value)
    assert unpackb(packed, strict_map_key=False) == value


def test_extra_data_raises() -> None:
    packed = packb(1) + b"\x00"
    with pytest.raises(ExtraData) as exc:
        unpackb(packed)
    assert exc.value.unpacked == 1
    assert exc.value.extra == b"\x00"


def test_ext_hook_transforms_extension() -> None:
    def hook(code: int, data: bytes):
        if code == 1:
            return int(data)
        return ExtType(code, data)

    packed = packb({"a": ExtType(1, b"123")})
    assert unpackb(packed, ext_hook=hook) == {"a": 123}


def test_format_error_on_invalid_bytes() -> None:
    with pytest.raises(FormatError):
        unpackb(b"\xc1")


def test_unpack_stream_reads_filelike() -> None:
    from featurelifted import unpack

    payload = packb({"k": "v"})
    assert unpack(BytesIO(payload)) == {"k": "v"}


def test_no_msgpack_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from msgpack|import msgpack)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
