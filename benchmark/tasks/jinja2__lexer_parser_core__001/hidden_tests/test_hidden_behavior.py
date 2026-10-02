from featurelifted import Environment
from featurelifted import nodes
from featurelifted.lexer import Lexer
from featurelifted.parser import Parser


def test_parse_for_loop_structure() -> None:
    env = Environment()
    tree = env.parse("{% for item in seq %}{{ item }}{% endfor %}")
    for_node = tree.body[0]
    assert isinstance(for_node, nodes.For)
    assert isinstance(for_node.body[0], nodes.Output)


def test_lexer_module_required_for_raw_blocks() -> None:
    env = Environment()
    lexer = Lexer(env)
    stream = lexer.tokenize("{% raw %}{{ x }}{% endraw %}")
    values = [token.value for token in stream if token.value]
    assert "{{ x }}" in values


def test_parser_module_required_for_if_elif() -> None:
    env = Environment()
    tree = Parser(env, "{% if a %}1{% elif b %}2{% else %}3{% endif %}").parse()
    if_node = tree.body[0]
    assert isinstance(if_node, nodes.If)
    assert len(if_node.elif_) == 1
