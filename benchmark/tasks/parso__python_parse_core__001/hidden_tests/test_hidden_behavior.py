from __future__ import annotations

import re
from pathlib import Path

from featurelifted import load_grammar, parse


def test_get_code_roundtrip() -> None:
    src = "def f(x):\n    return x + 1\n"
    module = parse(src, version="3.9")
    assert module.get_code() == src


def test_iter_errors_multiple() -> None:
    grammar = load_grammar(version="3.9")
    module = grammar.parse("foo +\nbar\ncontinue")
    errors = list(grammar.iter_errors(module))
    assert len(errors) >= 2


def test_parse_version_39() -> None:
    module = parse("match x:\n    case 1: pass", version="3.10")
    assert module.get_code().startswith("match")


def test_error_recovery_partial_tree() -> None:
    module = parse("def f(: pass", version="3.9")
    assert module.children


def test_no_parso_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from parso|import parso)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
