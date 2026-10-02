from __future__ import annotations

import pytest

from featurelifted import Lark, Tree, UnexpectedToken


GRAMMAR = r"""
start: expr
?expr: term (("+"|"-") term)*
?term: factor (("*"|"/") factor)*
?factor: NUMBER | "(" expr ")"
%import common.NUMBER
%import common.WS
%ignore WS
"""


def test_parse_builds_tree_with_precedence() -> None:
    parser = Lark(GRAMMAR, parser="lalr")
    tree = parser.parse("1 + 2 * 3")

    assert isinstance(tree, Tree)
    assert tree.data == "start"
    assert tree.children[0].data == "expr"


def test_parse_error_reports_unexpected_token() -> None:
    parser = Lark(GRAMMAR, parser="lalr")

    with pytest.raises(UnexpectedToken):
        parser.parse("1 + * 2")
