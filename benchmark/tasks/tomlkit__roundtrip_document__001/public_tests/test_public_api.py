from __future__ import annotations

from datetime import datetime
from datetime import timezone
from textwrap import dedent

import pytest

from featurelifted import array
from featurelifted import aot
from featurelifted import document
from featurelifted import dumps
from featurelifted import inline_table
from featurelifted import item
from featurelifted import parse
from featurelifted import string
from featurelifted.exceptions import ParseError
from featurelifted.exceptions import UnexpectedCharError


def test_parse_document_values_and_roundtrip_layout() -> None:
    content = dedent(
        """\
        # project metadata
        name = "featurelift"
        enabled = true
        ports = [8000, 8001, 8002]

        [owner]
        name = "Ada"
        dob = 1979-05-27T07:32:00Z

        [database]
        server = "192.168.1.1"
        connection_max = 5000
        """
    )

    doc = parse(content)

    assert doc["name"] == "featurelift"
    assert doc["enabled"] is True
    assert doc["ports"] == [8000, 8001, 8002]
    assert doc["owner"]["name"] == "Ada"
    assert doc["owner"]["dob"] == datetime(1979, 5, 27, 7, 32, tzinfo=timezone.utc)
    assert doc["database"]["connection_max"] == 5000
    assert doc.as_string() == content
    assert dumps(doc) == content


def test_editing_preserves_table_order_and_comments() -> None:
    content = dedent(
        """\
        [tool.poetry]
        name = "demo"

        [bar]
        name = "baz"

        [tool.poetry.dependencies]
        python = "^3.11"
        """
    )

    doc = parse(content)
    doc["tool"]["poetry"]["name"] = "featurelift"
    doc["tool"]["poetry"]["dependencies"]["pytest"] = "^8"

    assert doc.as_string() == dedent(
        """\
        [tool.poetry]
        name = "featurelift"

        [bar]
        name = "baz"

        [tool.poetry.dependencies]
        python = "^3.11"
        pytest = "^8"
        """
    )


def test_dump_plain_mappings_and_build_document() -> None:
    assert dumps({"project": {"name": "demo", "classifiers": ["A", "B"]}}) == dedent(
        """\
        [project]
        name = "demo"
        classifiers = ["A", "B"]
        """
    )
    assert dumps({"zzz": 1, "aaa": "foo"}, sort_keys=True) == 'aaa = "foo"\nzzz = 1\n'

    doc = document()
    doc.add("title", "Demo")
    doc.add("owner", {"name": "Ada", "active": True})

    assert dumps(doc) == dedent(
        """\
        title = "Demo"

        [owner]
        name = "Ada"
        active = true
        """
    )


def test_inline_table_array_and_parse_errors() -> None:
    table = inline_table()
    table.update({"version": "1.0", "optional": True})
    assert table.as_string() == '{version = "1.0", optional = true}'

    values = array()
    values.extend([1, 2, 3])
    assert values.as_string() == "[1, 2, 3]"

    dependencies = aot()
    dependencies.append(item({"name": "requests"}))
    assert item({"dependency": dependencies}).as_string() == dedent(
        """\
        [[dependency]]
        name = "requests"
        """
    )

    assert string('hello "world"').as_string() == '"hello \\"world\\""'
    assert string(r"C:\Users\Ada", literal=True).as_string() == "'C:\\Users\\Ada'"

    with pytest.raises(UnexpectedCharError) as excinfo:
        parse("a = [, 1]")

    assert isinstance(excinfo.value, ParseError)
    assert excinfo.value.line == 1
    assert excinfo.value.col == 5
