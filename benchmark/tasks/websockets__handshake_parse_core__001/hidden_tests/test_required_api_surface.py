"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Headers,
    Request,
    Response,
    accept_key,
    generate_key,
    validate_handshake_request,
    exceptions,
    headers,
    http11,
    streams,
)


def test_required_api_surface():
    assert isinstance(Headers, type)
    assert hasattr(Headers, 'get_all')
    assert hasattr(Headers, '__getitem__')
    assert isinstance(Request, type)
    assert hasattr(Request, 'parse')
    assert isinstance(Response, type)
    assert callable(accept_key)
    assert callable(generate_key)
    assert callable(validate_handshake_request)
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'InvalidHeader'), BaseException)
    assert issubclass(getattr(exceptions, 'InvalidHeaderFormat'), BaseException)
    assert issubclass(getattr(exceptions, 'InvalidHeaderValue'), BaseException)
    assert issubclass(getattr(exceptions, 'InvalidOrigin'), BaseException)
    assert issubclass(getattr(exceptions, 'InvalidUpgrade'), BaseException)
    assert issubclass(getattr(exceptions, 'SecurityError'), BaseException)
    assert headers is not None
    assert callable(getattr(headers, 'build_authorization_basic'))
    assert callable(getattr(headers, 'build_subprotocol'))
    assert callable(getattr(headers, 'build_www_authenticate_basic'))
    assert callable(getattr(headers, 'parse_authorization_basic'))
    assert callable(getattr(headers, 'parse_connection'))
    assert callable(getattr(headers, 'parse_extension'))
    assert callable(getattr(headers, 'parse_subprotocol'))
    assert callable(getattr(headers, 'parse_upgrade'))
    assert callable(getattr(headers, 'validate_subprotocols'))
    assert http11 is not None
    assert callable(getattr(http11, 'parse_headers'))
    assert streams is not None
    assert isinstance(getattr(streams, 'StreamReader'), type)
