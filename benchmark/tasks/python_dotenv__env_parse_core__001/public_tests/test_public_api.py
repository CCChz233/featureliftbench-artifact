from __future__ import annotations

import io

from featurelifted import dotenv_values, set_key


def test_dotenv_values_simple_pairs() -> None:
    stream = io.StringIO("FOO=bar\nBAZ=qux\n")
    assert dotenv_values(stream=stream) == {"FOO": "bar", "BAZ": "qux"}


def test_dotenv_values_quoted_value() -> None:
    stream = io.StringIO('GREETING="hello world"\n')
    assert dotenv_values(stream=stream) == {"GREETING": "hello world"}


def test_dotenv_values_export_prefix() -> None:
    stream = io.StringIO("export PORT=8000\n")
    assert dotenv_values(stream=stream) == {"PORT": "8000"}


def test_set_key_creates_file(tmp_path) -> None:
    env_path = tmp_path / ".env"
    result = set_key(env_path, "API_KEY", "secret")
    assert result == (True, "API_KEY", "secret")
    assert env_path.read_text() == "API_KEY='secret'\n"


def test_set_key_updates_existing(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=old\n")
    set_key(env_path, "FOO", "new")
    assert dotenv_values(stream=io.StringIO(env_path.read_text())) == {"FOO": "new"}
