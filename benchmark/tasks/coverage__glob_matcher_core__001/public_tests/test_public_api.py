from __future__ import annotations

import os

import pytest

from featurelifted import GlobMatcher
from featurelifted import globs_to_regex
from featurelifted import prep_patterns
from featurelifted.exceptions import ConfigError


def test_glob_matcher_matches_simple_patterns(tmp_path) -> None:
    root = tmp_path / "project"
    sub = root / "sub"
    sub.mkdir(parents=True)
    py_file = sub / "file1.py"
    py_file.write_text("x = 1\n", encoding="utf-8")

    matcher = GlobMatcher(["*.py", "*/sub2/*"], name="demo")
    assert matcher.match(str(py_file)) is True
    assert matcher.match(str(root / "sub" / "file2.c")) is False


def test_prep_patterns_adds_absolute_path(tmp_path) -> None:
    rel = "src/pkg"
    (tmp_path / rel).mkdir(parents=True)
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        patterns = prep_patterns([rel])
    finally:
        os.chdir(cwd)

    assert rel in patterns
    assert any(os.path.isabs(pattern) for pattern in patterns)


def test_globs_to_regex_rejects_invalid_pattern() -> None:
    with pytest.raises(ConfigError, match="can't include"):
        globs_to_regex(["***/bad"])
