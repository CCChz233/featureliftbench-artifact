"""Constitution API-surface coverage generated from public_spec."""

import featurelifted.h2.exceptions
import featurelifted.h2.frame_buffer
import featurelifted.hyperframe.exceptions
import featurelifted.hyperframe.frame

from featurelifted import (
    h2,
    hyperframe,
)


def test_required_api_surface():
    assert getattr(h2, 'exceptions') is not None
    assert issubclass(getattr(getattr(h2, 'exceptions'), 'FrameTooLargeError'), BaseException)
    assert issubclass(getattr(getattr(h2, 'exceptions'), 'ProtocolError'), BaseException)
    assert getattr(h2, 'frame_buffer') is not None
    assert isinstance(getattr(getattr(h2, 'frame_buffer'), 'FrameBuffer'), type)
    assert hasattr(getattr(getattr(h2, 'frame_buffer'), 'FrameBuffer'), 'add_data')
    assert getattr(getattr(h2, 'frame_buffer'), 'FrameBuffer') is not None
    assert getattr(hyperframe, 'exceptions') is not None
    assert issubclass(getattr(getattr(hyperframe, 'exceptions'), 'InvalidDataError'), BaseException)
    assert getattr(hyperframe, 'frame') is not None
    assert isinstance(getattr(getattr(hyperframe, 'frame'), 'ContinuationFrame'), type)
    assert getattr(getattr(hyperframe, 'frame'), 'ContinuationFrame') is not None
    assert getattr(getattr(hyperframe, 'frame'), 'ContinuationFrame') is not None
    assert hasattr(getattr(getattr(hyperframe, 'frame'), 'ContinuationFrame'), 'serialize')
    assert isinstance(getattr(getattr(hyperframe, 'frame'), 'DataFrame'), type)
    assert getattr(getattr(hyperframe, 'frame'), 'DataFrame') is not None
    assert hasattr(getattr(getattr(hyperframe, 'frame'), 'DataFrame'), 'serialize')
    assert isinstance(getattr(getattr(hyperframe, 'frame'), 'Frame'), type)
    assert isinstance(getattr(getattr(hyperframe, 'frame'), 'HeadersFrame'), type)
    assert getattr(getattr(hyperframe, 'frame'), 'HeadersFrame') is not None
    assert hasattr(getattr(getattr(hyperframe, 'frame'), 'HeadersFrame'), 'serialize')
    assert isinstance(getattr(getattr(hyperframe, 'frame'), 'PingFrame'), type)
