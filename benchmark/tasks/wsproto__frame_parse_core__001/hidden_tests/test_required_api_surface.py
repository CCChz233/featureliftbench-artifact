"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    frame_protocol,
)


def test_required_api_surface():
    assert frame_protocol is not None
    assert isinstance(getattr(frame_protocol, 'CloseReason'), type)
    assert isinstance(getattr(frame_protocol, 'FrameProtocol'), type)
    assert hasattr(getattr(frame_protocol, 'FrameProtocol'), 'close')
    assert hasattr(getattr(frame_protocol, 'FrameProtocol'), 'receive_bytes')
    assert hasattr(getattr(frame_protocol, 'FrameProtocol'), 'received_frames')
    assert issubclass(getattr(frame_protocol, 'ParseFailed'), BaseException)
