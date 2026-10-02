from __future__ import annotations

from pathlib import Path

import pytest

from featurelifted import Lark
from featurelifted.exceptions import GrammarError


def test_open_from_package_and_import_graph(tmp_path: Path) -> None:
    base = tmp_path / "pkg"
    grammars = base / "grammars"
    grammars.mkdir(parents=True)
    (grammars / "terminals.lark").write_text(
        'ESCAPED_STRING: /"[^"]*"/\n%ignore " "\n',
        encoding="utf-8",
    )
    (grammars / "main.lark").write_text(
        """start: greeting
greeting: "hi" | ESCAPED_STRING
%import .terminals.ESCAPED_STRING
""",
        encoding="utf-8",
    )
    parser = Lark.open(
        "grammars/main.lark",
        rel_to=str(base / "loader.py"),
        parser="lalr",
        import_paths=[str(base)],
    )
    assert parser.parse('"hello"')

    with pytest.raises(GrammarError):
        Lark('start: %import missing.rule\n', parser="lalr")


def test_packaged_common_grammar_import() -> None:
    import featurelifted
    from featurelifted.load_grammar import FromPackageLoader

    loader = FromPackageLoader(featurelifted.__name__, ("grammars",))
    parser = Lark(
        """start: NUMBER "+" NUMBER
%import common.NUMBER
%ignore " "
""",
        parser="lalr",
        import_paths=[loader],
    )
    tree = parser.parse("2+3")
    assert len(tree.children) == 2
    assert str(tree.children[0]) == "2"
