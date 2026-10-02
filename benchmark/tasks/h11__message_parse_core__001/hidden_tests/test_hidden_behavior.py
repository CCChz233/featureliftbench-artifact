from __future__ import annotations

from featurelifted import CLIENT, Connection, Data, EndOfMessage, Request, Response, SERVER
from featurelifted import NEED_DATA
from featurelifted import RemoteProtocolError


def _feed(conn: Connection, data: bytes):
    conn.receive_data(data)
    events = []
    while True:
        event = conn.next_event()
        if event is NEED_DATA:
            break
        events.append(event)
    return events


def test_chunked_response_body() -> None:
    conn = Connection(CLIENT)
    wire = (
        b"HTTP/1.1 200 OK\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"\r\n"
        b"5\r\n"
        b"hello\r\n"
        b"0\r\n"
        b"\r\n"
    )
    events = _feed(conn, wire)
    assert any(isinstance(e, Response) for e in events)
    data_events = [e for e in events if isinstance(e, Data)]
    assert b"".join(e.data for e in data_events) == b"hello"
    assert any(isinstance(e, EndOfMessage) for e in events)


def test_malformed_request_raises() -> None:
    conn = Connection(SERVER)
    conn.receive_data(b"NOT HTTP\r\n\r\n")
    try:
        conn.next_event()
        raised = False
    except RemoteProtocolError:
        raised = True
    assert raised
