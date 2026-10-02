from __future__ import annotations

from featurelifted import format
from featurelifted import parse
from featurelifted import split
from featurelifted import sql
from featurelifted import tokens as T


def test_parse_returns_statement_tokens() -> None:
    statement = parse("select id, name from users where id = 1")[0]

    assert isinstance(statement, sql.Statement)
    assert statement.get_type() == "SELECT"
    flattened = [token for token in statement.flatten() if not token.is_whitespace]
    assert flattened[0].value == "select"
    assert flattened[0].ttype is T.Keyword.DML
    assert [token.value for token in flattened[:5]] == ["select", "id", ",", "name", "from"]


def test_split_respects_quoted_semicolons() -> None:
    script = "select ';' as semi; select 2;"

    assert split(script, strip_semicolon=True) == ["select ';' as semi", "select 2"]


def test_format_supports_common_options() -> None:
    formatted = format(
        "select a,b from t where a=1 and b=2",
        keyword_case="upper",
        reindent=True,
        use_space_around_operators=True,
    )

    assert formatted == "SELECT a,\n       b\nFROM t\nWHERE a = 1\n  AND b = 2"
