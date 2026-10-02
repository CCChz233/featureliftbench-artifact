from __future__ import annotations

from featurelifted import CLIENT, Connection, NEED_DATA, Request, SERVER


def _collect(conn: Connection, data: bytes):
    conn.receive_data(data)
    events = []
    while True:
        event = conn.next_event()
        if event is NEED_DATA:
            break
        events.append(event)
    return events


def test_parse_simple_http_request() -> None:
    conn = Connection(SERVER)
    events = _collect(
        conn,
        b"GET /hello HTTP/1.1\r\nHost: example.com\r\n\r\n",
    )
    assert len(events) == 2
    assert events[0].method == b"GET"
    assert events[0].target == b"/hello"
    assert events[1].__class__.__name__ == "EndOfMessage"


def test_client_request_serialization() -> None:
    conn = Connection(CLIENT)
    payload = conn.send(Request(method="GET", target="/", headers=[("Host", "example.com")]))
    assert b"GET / HTTP/1.1" in payload
