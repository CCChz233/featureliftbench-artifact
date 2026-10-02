from __future__ import annotations

import datetime as dt
import os
import re
from pathlib import Path

import pytest

from featurelifted import Env, EnvError, EnvValidationError, validate


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Env:
    for key in list(os.environ):
        if key.startswith("FLB_"):
            monkeypatch.delenv(key, raising=False)
    return Env()


def test_list_subcast_int(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLB_LIST", "1,2,3")
    assert env.list("FLB_LIST", subcast=int) == [1, 2, 3]


def test_dict_subcast_values(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLB_DICT", "a=1,b=2")
    assert env.dict("FLB_DICT", subcast_values=int) == {"a": 1, "b": 2}


def test_expand_vars_with_default(monkeypatch: pytest.MonkeyPatch) -> None:
    expand_env = Env(expand_vars=True)
    monkeypatch.setenv("FLB_MAIN_DEF", "${FLB_MISSING:-maindef}")
    assert expand_env.str("FLB_MAIN_DEF") == "maindef"


def test_expand_vars_multiple_in_string(monkeypatch: pytest.MonkeyPatch) -> None:
    expand_env = Env(expand_vars=True)
    monkeypatch.setenv("FLB_USER", "gnarvaja")
    monkeypatch.setenv("FLB_PGURL", "postgres://${FLB_USER:-sloria}:${FLB_PASS:-secret}@localhost")
    assert expand_env.str("FLB_PGURL") == "postgres://gnarvaja:secret@localhost"


def test_marshmallow_range_validator(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLB_PORT", "70000")
    with pytest.raises(EnvError, match="invalid"):
        env.int("FLB_PORT", validate=validate.Range(min=1, max=65535))


def test_deferred_seal_aggregates_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    lazy = Env(eager=False)
    monkeypatch.setenv("FLB_INT", "not-an-int")
    monkeypatch.delenv("FLB_REQUIRED", raising=False)
    lazy.int("FLB_INT")
    lazy.str("FLB_REQUIRED")
    with pytest.raises(EnvValidationError) as excinfo:
        lazy.seal()
    messages = excinfo.value.error_messages
    assert "FLB_INT" in messages
    assert "FLB_REQUIRED" in messages


def test_timedelta_gep2257_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLB_TD", "42w 42d 42h 42m 42s 42ms 42us")
    assert Env().timedelta("FLB_TD") == dt.timedelta(
        weeks=42,
        days=42,
        hours=42,
        minutes=42,
        seconds=42,
        milliseconds=42,
        microseconds=42,
    )


def test_prefixed_context_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLB_APP_STR", "hello")
    base = Env()
    with base.prefixed("FLB_APP_"):
        assert base.str("STR") == "hello"


def test_no_environs_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from environs|import environs)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
