from __future__ import annotations

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
