from __future__ import annotations

from featurelifted._parsers import Encoder, _RESP2Parser, _RESP3Parser
from featurelifted.exceptions import ResponseError


class _FakeSocket:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._pos = 0

    def recv(self, size: int) -> bytes:
        chunk = self._payload[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def settimeout(self, _timeout) -> None:
        return None


class _FakeConnection:
    def __init__(self, payload: bytes, *, decode: bool = True) -> None:
        self.encoder = Encoder("utf-8", "strict", decode)
        self.socket_timeout = None
        self._sock = _FakeSocket(payload)


def test_resp2_error_reply_returns_response_error() -> None:
    parser = _RESP2Parser(4096)
    parser.on_connect(_FakeConnection(b"-ERR unknown command\r\n"))
    result = parser.read_response()
    assert isinstance(result, ResponseError)
    assert "unknown command" in str(result)


def test_resp3_null_and_boolean() -> None:
    parser = _RESP3Parser(4096)
    parser.on_connect(_FakeConnection(b"_\r\n"))
    assert parser.read_response() is None

    parser.on_connect(_FakeConnection(b"#t\r\n"))
    assert parser.read_response() is True


def test_encoder_rejects_bool() -> None:
    enc = Encoder("utf-8", "strict", True)
    try:
        enc.encode(True)
        raised = False
    except Exception:
        raised = True
    assert raised
