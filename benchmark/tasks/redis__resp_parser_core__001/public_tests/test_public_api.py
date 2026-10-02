from __future__ import annotations

from featurelifted._parsers import Encoder, _RESP2Parser


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
    def __init__(self, payload: bytes) -> None:
        self.encoder = Encoder("utf-8", "strict", True)
        self.socket_timeout = None
        self._sock = _FakeSocket(payload)


def test_resp2_simple_and_bulk_replies() -> None:
    parser = _RESP2Parser(4096)
    parser.on_connect(_FakeConnection(b":42\r\n"))
    assert parser.read_response() == 42

    parser.on_connect(_FakeConnection(b"$3\r\nfoo\r\n"))
    assert parser.read_response() == "foo"


def test_resp2_array_reply() -> None:
    parser = _RESP2Parser(4096)
    parser.on_connect(_FakeConnection(b"*2\r\n:1\r\n:2\r\n"))
    assert parser.read_response() == [1, 2]
