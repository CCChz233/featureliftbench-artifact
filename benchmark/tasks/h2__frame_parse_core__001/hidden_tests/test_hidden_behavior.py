from __future__ import annotations

import pytest

from featurelifted.h2.exceptions import FrameTooLargeError, ProtocolError
from featurelifted.h2.frame_buffer import FrameBuffer
from featurelifted.hyperframe.exceptions import InvalidDataError
from featurelifted.hyperframe.frame import (
    ContinuationFrame,
    DataFrame,
    Frame,
    HeadersFrame,
    PingFrame,
)


def test_ping_stream_id_must_be_zero() -> None:
    with pytest.raises(InvalidDataError):
        PingFrame(1)


def test_frame_buffer_rejects_bad_preamble() -> None:
    buf = FrameBuffer(server=True)
    with pytest.raises(ProtocolError):
        buf.add_data(b"NOTHTTP2")


def test_frame_buffer_enforces_max_frame_size() -> None:
    buf = FrameBuffer()
    buf.max_frame_size = 4
    frame = DataFrame(1)
    frame.data = b"12345"
    with pytest.raises(FrameTooLargeError):
        buf.add_data(frame.serialize())
        list(buf)


def test_continuation_reassembly() -> None:
    buf = FrameBuffer()
    buf.max_frame_size = 16384
    headers = HeadersFrame(3)
    headers.data = b"part-a"
    cont = ContinuationFrame(3)
    cont.data = b"part-b"
    cont.flags.add("END_HEADERS")
    buf.add_data(headers.serialize() + cont.serialize())
    out = list(buf)
    assert len(out) == 1
    assert isinstance(out[0], HeadersFrame)
    assert out[0].data == b"part-apart-b"
