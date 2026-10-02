from __future__ import annotations

import os

from featurelifted import SourceSelector


def test_source_selector_honors_source_tree(tmp_path) -> None:
    src = tmp_path / "src"
    pkg = src / "pkg"
    pkg.mkdir(parents=True)
    inside = pkg / "mod.py"
    inside.write_text("x = 1\n", encoding="utf-8")
    outside = tmp_path / "outside.py"
    outside.write_text("y = 2\n", encoding="utf-8")

    selector = SourceSelector(source=[str(src)])

    assert selector.skip_reason(str(inside)) is None
    assert selector.skip_reason(str(outside)) is not None
    assert "falls outside" in selector.skip_reason(str(outside))


def test_source_selector_honors_omit(tmp_path) -> None:
    src = tmp_path / "src"
    tests = src / "tests"
    tests.mkdir(parents=True)
    test_file = tests / "test_x.py"
    test_file.write_text("def test_x():\n    pass\n", encoding="utf-8")

    selector = SourceSelector(source=[str(src)], run_omit=["*/tests/*"])

    reason = selector.skip_reason(str(test_file))
    assert reason is not None
    assert "omit" in reason
