from __future__ import annotations

from pathlib import Path

from featurelifted import Lark


def test_open_relative_import_and_common_import(tmp_path: Path) -> None:
    grammar_dir = tmp_path / "grammars"
    grammar_dir.mkdir()
    (grammar_dir / "tokens.lark").write_text('NUMBER: /[0-9]+/\n', encoding="utf-8")
    (grammar_dir / "calc.lark").write_text(
        """start: sum
?sum: product | sum "+" product -> add
?product: atom | product "*" atom -> mul
?atom: NUMBER | "(" sum ")"
%import .tokens.NUMBER
%ignore " "
""",
        encoding="utf-8",
    )
    parser = Lark.open("calc.lark", rel_to=str(grammar_dir / "calc.lark"), parser="lalr")
    tree = parser.parse("1+2*3")
    assert "add" in tree.pretty()

    import featurelifted
    from featurelifted.load_grammar import FromPackageLoader

    loader = FromPackageLoader(featurelifted.__name__, ("grammars",))
    common_parser = Lark(
        "start: NUMBER\n%import common.NUMBER",
        parser="lalr",
        import_paths=[loader],
    )
    assert common_parser.parse("42")
