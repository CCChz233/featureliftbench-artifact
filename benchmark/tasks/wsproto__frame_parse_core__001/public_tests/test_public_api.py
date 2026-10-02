from __future__ import annotations

from featurelifted.frame_protocol import FrameProtocol


def test_client_receives_unmasked_text() -> None:
    fp = FrameProtocol(client=True, extensions=[])
    fp.receive_bytes(b"\x81\x05hello")
    frame = next(fp.received_frames())
    assert frame.payload == "hello"


def test_client_send_data() -> None:
    fp = FrameProtocol(client=True, extensions=[])
    out = fp.send_data("hi", fin=True)
    assert out[0] & 0x0F == 0x1
