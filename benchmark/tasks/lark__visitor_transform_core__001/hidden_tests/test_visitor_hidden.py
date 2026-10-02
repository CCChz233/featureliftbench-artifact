from __future__ import annotations

from featurelifted import Discard, Lark, Transformer, Tree, Visitor, v_args


class DropSemi(Transformer):
    def NUMBER(self, token):
        return int(token)

    def semicolon(self, _token):
        return Discard

    def num(self, children):
        return children[0]

    def nums(self, children):
        return [child for child in children if child is not Discard]

    def start(self, children):
        return children[0]


def test_discard_removes_nodes() -> None:
    grammar = r"""
start: nums
nums: num+
?num: NUMBER | semicolon
semicolon: ";"
NUMBER: /\d+/
%import common.WS
%ignore WS
"""
    parser = Lark(grammar, parser="lalr")
    tree = parser.parse("1;2;;3;")
    values = DropSemi().transform(tree)

    assert values == [1, 2, 3]


class Counter(Visitor):
    def __init__(self) -> None:
        self.seen: list[str] = []

    def __default__(self, tree: Tree) -> None:
        self.seen.append(tree.data)


def test_visitor_walks_tree_nodes() -> None:
    grammar = r"""
start: pair pair
pair: "(" NUMBER ")"
NUMBER: /\d+/
%import common.WS
%ignore WS
"""
    parser = Lark(grammar, parser="lalr")
    tree = parser.parse("(1)(2)")
    counter = Counter()
    counter.visit(tree)

    assert "start" in counter.seen
    assert counter.seen.count("pair") == 2


class UpperNames(Transformer):
    def name(self, children):
        return children[0].value.upper()

    def start(self, children):
        return children[0]


def test_v_args_tree_mode() -> None:
    grammar = r"""
start: name
name: /[a-z]+/
%import common.WS
%ignore WS
"""
    parser = Lark(grammar, parser="lalr")
    tree = parser.parse("lark")
    assert UpperNames().transform(tree) == "LARK"
