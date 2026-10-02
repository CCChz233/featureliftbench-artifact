from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import Headers, Request, validate_handshake_request
from featurelifted.exceptions import (
    InvalidHeader,
    InvalidHeaderFormat,
    InvalidHeaderValue,
    InvalidOrigin,
    InvalidUpgrade,
    SecurityError,
)
from featurelifted.headers import (
    build_authorization_basic,
    build_subprotocol,
    build_www_authenticate_basic,
    parse_authorization_basic,
    parse_extension,
    parse_subprotocol,
    parse_upgrade,
    validate_subprotocols,
)
from featurelifted.http11 import parse_headers
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


def _drive_headers_parse(data: bytes):
    reader = StreamReader()
    reader.feed_data(data)
    gen = parse_headers(reader.read_line)
    while True:
        try:
            next(gen)
        except StopIteration as exc:
            return exc.value


def _valid_request(extra_headers: bytes = b"") -> Request:
    data = (
        b"GET /chat HTTP/1.1\r\n"
        b"Host: server.example.com\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        b"Sec-WebSocket-Version: 13\r\n"
        + extra_headers
        + b"\r\n"
    )
    return _drive_request_parse(data)


def test_parse_extension_with_quoted_params() -> None:
    header = (
        'foo; name; token=token; quoted-string="quoted-string", '
        "bar; quux; quuux"
    )
    parsed = parse_extension(header)
    assert parsed == [
        (
            "foo",
            [
                ("name", None),
                ("token", "token"),
                ("quoted-string", "quoted-string"),
            ],
        ),
        ("bar", [("quux", None), ("quuux", None)]),
    ]


def test_parse_upgrade_case_insensitive_list() -> None:
    assert parse_upgrade(",,  WebSocket,  \t,,") == ["WebSocket"]


def test_parse_subprotocol_skips_empty_elements() -> None:
    assert parse_subprotocol(",\t, ,  ,foo  ,,   bar,baz,,") == ["foo", "bar", "baz"]


def test_headers_multiple_connection_values() -> None:
    headers = Headers(
        [
            ("Connection", "keep-alive"),
            ("Connection", "Upgrade"),
            ("Upgrade", "websocket"),
        ]
    )
    assert headers.get_all("connection") == ["keep-alive", "Upgrade"]
    with pytest.raises(Exception):
        _ = headers["connection"]


def test_validate_handshake_rejects_bad_upgrade() -> None:
    request = _valid_request(b"Upgrade: http/1.1\r\n")
    with pytest.raises(InvalidUpgrade):
        validate_handshake_request(request)


def test_validate_handshake_missing_key() -> None:
    data = (
        b"GET /chat HTTP/1.1\r\n"
        b"Host: server.example.com\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Version: 13\r\n"
        b"\r\n"
    )
    request = _drive_request_parse(data)
    with pytest.raises(InvalidHeader):
        validate_handshake_request(request)


def test_validate_handshake_invalid_key_length() -> None:
    data = (
        b"GET /chat HTTP/1.1\r\n"
        b"Host: server.example.com\r\n"
        b"Upgrade: websocket\r\n"
        b"Connection: Upgrade\r\n"
        b"Sec-WebSocket-Key: dGhl\r\n"
        b"Sec-WebSocket-Version: 13\r\n"
        b"\r\n"
    )
    request = _drive_request_parse(data)
    with pytest.raises(InvalidHeaderValue):
        validate_handshake_request(request)


def test_validate_handshake_origin_allowlist() -> None:
    request = _valid_request(b"Origin: http://evil.example\r\n")
    with pytest.raises(InvalidOrigin):
        validate_handshake_request(
            request,
            origins=["http://example.com"],
        )


def test_parse_request_invalid_method() -> None:
    data = b"OPTIONS * HTTP/1.1\r\n\r\n"
    with pytest.raises(ValueError, match="unsupported HTTP method"):
        _drive_request_parse(data)


def test_parse_headers_security_limit() -> None:
    data = b"foo: bar\r\n" * 129 + b"\r\n"
    with pytest.raises(SecurityError):
        _drive_headers_parse(data)


def test_parse_extension_invalid_quoted_token() -> None:
    with pytest.raises(InvalidHeaderFormat):
        parse_extension('foo; bar=" "')


def test_build_subprotocol_roundtrip() -> None:
    subprotocols = ["chat", "superchat"]
    validate_subprotocols(subprotocols)
    header = build_subprotocol(subprotocols)
    assert parse_subprotocol(header) == subprotocols


def test_validate_subprotocols_rejects_invalid_token() -> None:
    with pytest.raises(ValueError, match="invalid subprotocol"):
        validate_subprotocols(["bad token"])


def test_parse_authorization_basic_credentials() -> None:
    header = build_authorization_basic("alice", "s3cret!")
    assert parse_authorization_basic(header) == ("alice", "s3cret!")


def test_parse_authorization_basic_rejects_non_basic_scheme() -> None:
    with pytest.raises(InvalidHeaderValue, match="unsupported scheme"):
        parse_authorization_basic("Bearer token")


def test_build_www_authenticate_basic_format() -> None:
    header = build_www_authenticate_basic("example")
    assert header.startswith("Basic realm=")
    assert "charset=" in header


def test_validate_handshake_origin_regex_allowlist() -> None:
    request = _valid_request(b"Origin: https://app.example.com\r\n")
    assert validate_handshake_request(
        request,
        origins=[re.compile(r"https://.*\.example\.com")],
    )


def test_no_websockets_import_surface() -> None:
    import featurelifted

    forbidden = {"connect", "serve", "ClientConnection", "ServerConnection"}
    for name in forbidden:
        assert not hasattr(featurelifted, name), f"unexpected network API: {name}"

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from websockets|import websockets)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
