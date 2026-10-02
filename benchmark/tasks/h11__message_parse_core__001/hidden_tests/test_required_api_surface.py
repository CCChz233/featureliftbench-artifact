"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Connection,
    CLIENT,
    SERVER,
    Request,
    Response,
    Data,
    EndOfMessage,
    NEED_DATA,
    RemoteProtocolError,
)


def test_required_api_surface():
    assert isinstance(Connection, type)
    assert hasattr(Connection, 'next_event')
    assert hasattr(Connection, 'receive_data')
    assert isinstance(CLIENT, type)
    assert isinstance(SERVER, type)
    assert isinstance(Request, type)
    assert isinstance(Response, type)
    assert isinstance(Data, type)
    assert isinstance(EndOfMessage, type)
    assert isinstance(NEED_DATA, type)
    assert issubclass(RemoteProtocolError, BaseException)
