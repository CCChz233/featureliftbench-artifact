from featurelifted import Environment
from featurelifted import nodes


def test_parse_variable_output() -> None:
    env = Environment()
    tree = env.parse("Hello {{ name }}!")
    assert isinstance(tree, nodes.Template)
    assert len(tree.body) == 1
    output = tree.body[0]
    assert isinstance(output, nodes.Output)
    assert any(isinstance(node, nodes.Name) and node.name == "name" for node in output.nodes)


def test_lex_returns_token_types() -> None:
    env = Environment()
    tokens = list(env.lex("{% if x %}y{% endif %}"))
    types = [t[1] for t in tokens if t[1] != "eof"]
    assert "block_begin" in types
    assert "name" in types
