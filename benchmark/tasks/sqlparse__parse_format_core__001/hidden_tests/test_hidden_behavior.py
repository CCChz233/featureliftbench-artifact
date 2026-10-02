from __future__ import annotations

import pytest

from featurelifted import format
from featurelifted import parse
from featurelifted import split
from featurelifted import sql
from featurelifted.exceptions import SQLParseError


def test_split_handles_comments_and_embedded_semicolons() -> None:
    script = "select 1; -- keep ; comment\nselect ';';"

    assert split(script, strip_semicolon=True) == [
        "select 1; -- keep ; comment",
        "select ';'",
    ]


def test_cte_aliases_and_identifier_helpers() -> None:
    statement = parse(
        "WITH cte AS (SELECT id FROM users) "
        "SELECT cte.id AS user_id FROM cte JOIN logs ON logs.user_id = cte.id"
    )[0]

    assert statement.get_type() == "SELECT"
    identifiers = []
    for token in statement.tokens:
        if isinstance(token, sql.Identifier):
            identifiers.append((token.value, token.get_name(), token.get_real_name(), token.get_alias()))

    assert ("cte AS (SELECT id FROM users)", "cte", "cte", None) in identifiers
    assert ("cte.id AS user_id", "user_id", "id", "user_id") in identifiers
    assert ("logs", "logs", "logs", None) in identifiers


def test_token_navigation_and_ancestor_relationships() -> None:
    statement = parse("select * from users where id = 1 and active = true")[0]
    where = next(token for token in statement.tokens if isinstance(token, sql.Where))

    index, comparison = where.token_next(0, skip_ws=True)

    assert index == 2
    assert isinstance(comparison, sql.Comparison)
    assert comparison.value == "id = 1"
    assert comparison.within(sql.Where)
    assert comparison.has_ancestor(where)


def test_formatter_comment_stripping_and_spacing() -> None:
    assert (
        format(
            "select a, -- inline\n b from t",
            strip_comments=True,
            reindent=True,
            keyword_case="upper",
        )
        == "SELECT a, b\nFROM t"
    )

    assert (
        format("select a+b as total from t", use_space_around_operators=True)
        == "select a + b as total from t"
    )


def test_formatter_rejects_invalid_options() -> None:
    with pytest.raises(SQLParseError, match="Invalid value for keyword_case"):
        format("select 1", keyword_case="invalid")
