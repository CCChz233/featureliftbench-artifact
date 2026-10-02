from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from featurelifted import dotenv_values, set_key


def test_double_quote_escape_sequences() -> None:
    stream = io.StringIO(r'a="b\nc"' + "\n")
    assert dotenv_values(stream=stream)["a"] == "b\nc"


def test_single_quote_escape_only_backslash_and_quote() -> None:
    stream = io.StringIO(r"a='b\\nc'" + "\n")
    assert dotenv_values(stream=stream)["a"] == r"b\nc"


def test_utf8_bom_stripped() -> None:
    stream = io.StringIO("\ufeffKEY=value\n")
    assert dotenv_values(stream=stream) == {"KEY": "value"}


def test_inline_comment_after_whitespace() -> None:
    stream = io.StringIO("FOO=bar # comment\n")
    assert dotenv_values(stream=stream) == {"FOO": "bar"}


def test_key_without_value_is_none() -> None:
    stream = io.StringIO("EMPTY_VAR\n")
    assert dotenv_values(stream=stream) == {"EMPTY_VAR": None}


def test_variable_interpolation_chain() -> None:
    stream = io.StringIO("BASE=hello\nFULL=${BASE} world\n")
    assert dotenv_values(stream=stream)["FULL"] == "hello world"


def test_variable_default_when_missing() -> None:
    stream = io.StringIO("X=${MISSING:-fallback}\n")
    assert dotenv_values(stream=stream)["X"] == "fallback"


def test_set_key_quotes_special_characters(tmp_path) -> None:
    env_path = tmp_path / ".env"
    set_key(env_path, "MSG", 'say "hi"')
    assert env_path.read_text() == "MSG='say \"hi\"'\n"


def test_set_key_appends_without_trailing_newline(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("A=1")
    set_key(env_path, "B", "2")
    text = env_path.read_text()
    assert text == "A=1\nB='2'\n"
    assert dotenv_values(stream=io.StringIO(text)) == {"A": "1", "B": "2"}


def test_no_dotenv_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from dotenv|import dotenv)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
