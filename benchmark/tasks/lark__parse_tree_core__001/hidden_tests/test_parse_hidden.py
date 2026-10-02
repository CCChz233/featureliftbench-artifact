from __future__ import annotations

import pytest

from featurelifted import Lark, Tree, UnexpectedCharacters, UnexpectedToken


LIST_GRAMMAR = r"""
start: "[" items "]"
items: item ("," item)*
item: NAME | NUMBER
%import common.NUMBER
%import common.CNAME -> NAME
%import common.WS
%ignore WS
"""


def test_nested_lists_and_tokens() -> None:
    parser = Lark(LIST_GRAMMAR, parser="lalr")
    tree = parser.parse("[a, 1, b]")

    assert tree.data == "start"
    items = tree.children[0]
    assert items.data == "items"
    assert len(items.children) == 3


def test_unexpected_characters_on_garbage_input() -> None:
    parser = Lark(LIST_GRAMMAR, parser="lalr")

    with pytest.raises((UnexpectedToken, UnexpectedCharacters)):
        parser.parse("[a @ b]")


def test_named_terminal_and_pretty_output() -> None:
    grammar = r"""
start: greet
greet: "hello" NAME
NAME: /[A-Za-z]+/
%import common.WS
%ignore WS
"""
    parser = Lark(grammar, parser="lalr")
    tree = parser.parse("hello Ada")

    pretty = tree.pretty()
    assert "greet" in pretty
    assert "Ada" in pretty
    assert tree.children[0].data == "greet"
