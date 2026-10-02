"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse,
    loads,
    dumps,
    document,
    table,
    inline_table,
    array,
    aot,
    string,
    item,
    exceptions,
)


def test_required_api_surface():
    assert callable(parse)
    assert callable(loads)
    assert callable(dumps)
    assert callable(document)
    assert callable(table)
    assert callable(inline_table)
    assert callable(array)
    assert callable(aot)
    assert callable(string)
    assert callable(item)
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'InvalidUnicodeValueError'), BaseException)
    assert issubclass(getattr(exceptions, 'ParseError'), BaseException)
    assert issubclass(getattr(exceptions, 'UnexpectedCharError'), BaseException)
