"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    EndOfList,
    JsonPointer,
    JsonPointerException,
    resolve_pointer,
    set_pointer,
    escape,
    unescape,
)


def test_required_api_surface():
    assert isinstance(EndOfList, type)
    assert isinstance(JsonPointer, type)
    assert hasattr(JsonPointer, 'from_parts')
    assert hasattr(JsonPointer, 'get_parts')
    assert JsonPointer is not None
    assert hasattr(JsonPointer, '__contains__')
    assert issubclass(JsonPointerException, BaseException)
    assert callable(resolve_pointer)
    assert callable(set_pointer)
    assert callable(escape)
    assert callable(unescape)
