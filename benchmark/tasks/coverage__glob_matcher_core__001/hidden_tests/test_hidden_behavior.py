from __future__ import annotations

import os

from featurelifted import GlobMatcher


def test_glob_matcher_respects_windows_style_paths(tmp_path) -> None:
    root = tmp_path / "dir"
    root.mkdir()
    target = root / "foo.py"
    target.write_text("pass\n", encoding="utf-8")

    matcher = GlobMatcher(["*/foo.py"])
    assert matcher.match(str(target)) is True
    assert matcher.match(os.path.join("dir", "foo.py")) is True


def test_glob_matcher_many_patterns(tmp_path) -> None:
    matcher = GlobMatcher([f"*x{i:03d}*.txt" for i in range(500)])
    assert matcher.match("x123foo.txt") is True
    assert matcher.match("x798bar.txt") is False


def test_glob_matcher_backslash_pattern(tmp_path) -> None:
    matcher = GlobMatcher([r"*\foo.py"])
    assert matcher.match(r"dir\foo.py") is True


def test_glob_matcher_question_mark_single_char() -> None:
    matcher = GlobMatcher(["file?.py"])
    assert matcher.match("file1.py") is True
    assert matcher.match("file12.py") is False
