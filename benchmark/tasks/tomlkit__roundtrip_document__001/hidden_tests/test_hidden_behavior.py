from __future__ import annotations

from textwrap import dedent

import pytest

from featurelifted import aot
from featurelifted import array
from featurelifted import dumps
from featurelifted import item
from featurelifted import loads
from featurelifted import parse
from featurelifted import string
from featurelifted.exceptions import InvalidUnicodeValueError
from featurelifted.exceptions import ParseError


def test_multiline_literal_strings_and_trailing_comma_arrays_roundtrip() -> None:
    content = (
        'numbers = [1, 2, ]\n'
        'text = """\nhello\n"""\n'
        "literal = '''C:\\Users\\Ada'''\n"
    )

    doc = parse(content)

    assert doc["numbers"] == [1, 2]
    assert doc["text"] == "hello\n"
    assert doc["literal"] == r"C:\Users\Ada"
    assert doc.as_string() == content


def test_arrays_of_tables_and_inline_tables_dump_correctly() -> None:
    dependencies = aot()
    first = item({"name": "requests", "version": "^2.31"})
    second = item({"name": "pytest", "version": "^8", "optional": True})
    dependencies.append(first)
    dependencies.append(second)

    doc = item({"dependency": dependencies})

    assert doc.as_string() == dedent(
        """\
        [[dependency]]
        name = "requests"
        version = "^2.31"

        [[dependency]]
        name = "pytest"
        version = "^8"
        optional = true
        """
    )

    arr = array()
    arr.extend([{"x": 1}, {"x": 2}])
    assert arr.as_string() == '[{x = 1}, {x = 2}]'


def test_dotted_keys_table_redefinition_and_unicode_errors() -> None:
    doc = loads('a.b.c = 1\nsite."google.com" = true\n')

    assert doc["a"]["b"]["c"] == 1
    assert doc["site"]["google.com"] is True

    with pytest.raises(ParseError):
        parse("[a.b]\n[a]\n[a.b]\n")

    with pytest.raises(InvalidUnicodeValueError) as excinfo:
        parse(r'a = "\uD800"')

    assert excinfo.value.line == 1
    assert excinfo.value.col == 6


def test_string_constructor_and_sorted_dump_preserve_expected_format() -> None:
    basic = string('hello "world"')
    literal = string(r"C:\Users\Ada", literal=True)
    multiline = string("first\nsecond\n", multiline=True)

    assert basic.as_string() == '"hello \\"world\\""'
    assert literal.as_string() == "'C:\\Users\\Ada'"
    assert multiline.as_string() == '"""first\nsecond\n"""'

    doc = parse('zzz = 1\naaa = "foo"\n')
    assert dumps(doc, sort_keys=True) == 'aaa = "foo"\nzzz = 1\n'
