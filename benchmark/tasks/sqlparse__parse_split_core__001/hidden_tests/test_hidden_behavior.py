from __future__ import annotations

from featurelifted import parse
from featurelifted import split


def test_split_handles_comments_and_embedded_semicolons() -> None:
    script = "select 1; -- keep ; comment\nselect ';';"

    assert split(script, strip_semicolon=True) == [
        "select 1; -- keep ; comment",
        "select ';'",
    ]


def test_parse_multiple_statements() -> None:
    statements = parse("select 1; select 2")

    assert len(statements) == 2
    assert statements[0].get_type() == "SELECT"
    assert statements[1].get_type() == "SELECT"
