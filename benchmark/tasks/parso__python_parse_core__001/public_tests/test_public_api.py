from __future__ import annotations

from featurelifted import parse


def test_parse_simple_expr() -> None:
    module = parse("1 + 2", version="3.9")
    expr = module.children[0]
    assert expr.get_code().strip() == "1 + 2"


def test_name_node_positions() -> None:
    module = parse("hello", version="3.9")
    name = module.children[0]
    assert name.start_pos == (1, 0)
    assert name.value == "hello"
