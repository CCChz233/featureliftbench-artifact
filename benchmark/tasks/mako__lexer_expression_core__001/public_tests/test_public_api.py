from __future__ import annotations

from featurelifted import Lexer, parsetree
from featurelifted import PythonCode


def test_parse_text_and_expression() -> None:
    node = Lexer("Hello ${name}!").parse()
    assert isinstance(node, parsetree.TemplateNode)
    assert len(node.nodes) == 3
    assert isinstance(node.nodes[0], parsetree.Text)
    assert isinstance(node.nodes[1], parsetree.Expression)
    assert node.nodes[1].text == "name"
    assert isinstance(node.nodes[2], parsetree.Text)


def test_parse_control_line() -> None:
    node = Lexer("% if flag:\n    hi\n% endif\n").parse()
    assert isinstance(node.nodes[0], parsetree.ControlLine)
    assert node.nodes[0].keyword == "if"
    assert node.nodes[0].text == "if flag:"
    assert isinstance(node.nodes[2], parsetree.ControlLine)
    assert node.nodes[2].isend is True


def test_python_code_undeclared() -> None:
    parsed = PythonCode("x + y * z")
    assert parsed.undeclared_identifiers == {"x", "y", "z"}
    assert parsed.declared_identifiers == set()


def test_def_tag_parses() -> None:
    node = Lexer('<%def name="foo()">body</%def>').parse()
    tag = node.nodes[0]
    assert isinstance(tag, parsetree.DefTag)
    assert tag.keyword == "def"
    assert tag.attributes["name"] == "foo()"
