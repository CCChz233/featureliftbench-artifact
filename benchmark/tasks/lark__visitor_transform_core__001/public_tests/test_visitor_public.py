from __future__ import annotations

from featurelifted import Lark, Transformer, v_args


CALC_GRAMMAR = r"""
start: sum
?sum: product
    | sum "+" product -> add
    | sum "-" product -> sub
?product: atom
    | product "*" atom -> mul
    | product "/" atom -> div
?atom: NUMBER
%import common.NUMBER
%import common.WS
%ignore WS
"""


class CalcTransformer(Transformer):
    def NUMBER(self, token):
        return int(token)

    @v_args(inline=True)
    def add(self, left, right):
        return left + right

    @v_args(inline=True)
    def sub(self, left, right):
        return left - right

    @v_args(inline=True)
    def mul(self, left, right):
        return left * right

    @v_args(inline=True)
    def div(self, left, right):
        return left // right

    start = sum


def test_transformer_evaluates_expression() -> None:
    parser = Lark(CALC_GRAMMAR, parser="lalr")
    tree = parser.parse("1 + 2 * 3")
    value = CalcTransformer().transform(tree)

    assert value == 7


class InlineAdder(Transformer):
    def NUMBER(self, token):
        return int(token)

    @v_args(inline=True)
    def add(self, left, right):
        return left + right

    start = sum


def test_v_args_inline_transform() -> None:
    grammar = r"""
start: sum
sum: NUMBER "+" NUMBER -> add
%import common.NUMBER
%import common.WS
%ignore WS
"""
    parser = Lark(grammar, parser="lalr")
    tree = parser.parse("2+5")
    assert InlineAdder().transform(tree) == 7
