import pytest

from featurelifted import loads


def test_loads_parses_unquoted_keys_and_trailing_comma() -> None:
    value = loads("{name: 'widget', qty: 2,}")

    assert value == {"name": "widget", "qty": 2}


def test_loads_supports_line_comments() -> None:
    value = loads(
        """
        {
          // inventory item
          active: true,
          tags: ['sale', 'new',],
        }
        """
    )

    assert value["active"] is True
    assert value["tags"] == ["sale", "new"]
