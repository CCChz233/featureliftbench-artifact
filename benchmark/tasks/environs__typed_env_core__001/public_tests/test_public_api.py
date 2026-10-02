from __future__ import annotations

import os

import pytest

from featurelifted import Env, EnvError


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.delenv("INT_VAR", raising=False)
    monkeypatch.delenv("BOOL_VAR", raising=False)
    monkeypatch.delenv("STR_VAR", raising=False)
    return Env()


def test_int_cast(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INT_VAR", "42")
    assert env.int("INT_VAR") == 42


def test_bool_cast(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOL_VAR", "1")
    assert env.bool("BOOL_VAR") is True
    monkeypatch.setenv("BOOL_VAR", "0")
    assert env.bool("BOOL_VAR") is False


def test_str_default_when_unset(env: Env) -> None:
    assert env.str("STR_VAR", "fallback") == "fallback"


def test_missing_required_raises(env: Env) -> None:
    with pytest.raises(EnvError, match='Environment variable "INT_VAR" not set'):
        env.int("INT_VAR")
