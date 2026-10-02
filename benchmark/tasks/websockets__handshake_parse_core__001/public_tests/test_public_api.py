from __future__ import annotations

from featurelifted import Headers, Request, accept_key, generate_key
from featurelifted.headers import parse_connection, parse_upgrade
from featurelifted.streams import StreamReader


def _drive_request_parse(data: bytes) -> Request:
    reader = StreamReader()
    reader.feed_data(data)
    gen = Request.parse(reader.read_line)
    while True:
        try:
            next(gen)
        except StopIteration as exc:
            return exc.value


def test_parse_connection_and_upgrade() -> None:
    assert parse_connection("keep-alive, Upgrade") == ["keep-alive", "Upgrade"]
    assert parse_upgrade("websocket") == ["websocket"]


def test_headers_case_insensitive_lookup() -> None:
    headers = Headers([("Upgrade", "websocket"), ("Connection", "Upgrade")])
    assert headers["upgrade"] == "websocket"
    assert headers["CONNECTION"] == "Upgrade"


def test_parse_websocket_request_basic() -> None:
    data = (
        b"GET /chat HTTP/1.1\r\n"
        b"Host: server.example.com\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        b"Sec-WebSocket-Version: 13\r\n"
        b"\r\n"
    )
    request = _drive_request_parse(data)
    assert request.path == "/chat"
    assert request.headers["Host"] == "server.example.com"
    assert request.headers["Upgrade"] == "websocket"


def test_accept_key_rfc6455_example() -> None:
    assert accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
    key = generate_key()
    assert isinstance(key, str)
    assert len(key) > 0
