from __future__ import annotations

import re
from pathlib import Path

import pytest

from featurelifted import CompileException, Lexer, PythonFragment, SyntaxException, parsetree


def test_percent_escape_in_template() -> None:
    node = Lexer("%% literal\n% if x:\n% endif\n").parse()
    assert isinstance(node.nodes[0], parsetree.Text)
    assert node.nodes[0].content == "%"
    assert isinstance(node.nodes[2], parsetree.ControlLine)
    assert node.nodes[2].keyword == "if"


def test_unclosed_tag_raises_syntax() -> None:
    with pytest.raises(SyntaxException):
        Lexer('<%def name="foo()">\nbody\n').parse()


def test_python_fragment_for_loop() -> None:
    parsed = PythonFragment("for item in items:")
    assert parsed.declared_identifiers == {"item"}
    assert parsed.undeclared_identifiers == {"items"}


def test_expression_filter_escapes() -> None:
    node = Lexer("${value | h, trim}").parse()
    expr = node.nodes[0]
    assert isinstance(expr, parsetree.Expression)
    undeclared = expr.undeclared_identifiers()
    assert "value" in undeclared
    assert "h" not in undeclared
    assert "trim" not in undeclared


def test_elif_partial_control_identifiers() -> None:
    parsed = PythonFragment("elif cond and other:")
    assert "cond" in parsed.undeclared_identifiers
    assert "other" in parsed.undeclared_identifiers


def test_invalid_partial_control_raises_compile() -> None:
    with pytest.raises(CompileException):
        PythonFragment(
            "notcontrol at all",
            source="notcontrol at all",
            lineno=1,
            pos=1,
            filename=None,
        )


def test_no_mako_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from mako|import mako)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
