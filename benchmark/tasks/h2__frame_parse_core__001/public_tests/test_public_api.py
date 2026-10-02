from __future__ import annotations

from featurelifted.h2.frame_buffer import FrameBuffer
from featurelifted.hyperframe.frame import DataFrame, Frame, PingFrame


def test_ping_frame_roundtrip() -> None:
    raw = PingFrame(0).serialize()
    header = memoryview(raw)[:9]
    frame, _length = Frame.parse_frame_header(header)
    frame.parse_body(memoryview(raw)[9:])
    assert isinstance(frame, PingFrame)
    assert frame.stream_id == 0


def test_data_frame_via_frame_buffer() -> None:
    buf = FrameBuffer()
    buf.max_frame_size = 16384
    payload = DataFrame(1)
    payload.data = b"hello"
    buf.add_data(payload.serialize())
    frames = list(buf)
    assert len(frames) == 1
    assert frames[0].data == b"hello"
