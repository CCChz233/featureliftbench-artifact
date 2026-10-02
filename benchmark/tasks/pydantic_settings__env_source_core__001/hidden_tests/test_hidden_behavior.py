from __future__ import annotations

import json

import pytest
from pydantic import Field

from featurelifted import BaseSettings, SettingsConfigDict, SettingsError


class NestedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLB_", env_nested_delimiter="__")
    tags: list[str] = Field(default_factory=list)
    limits: dict = Field(default_factory=dict)


def test_json_list_env(monkeypatch) -> None:
    monkeypatch.setenv("FLB_TAGS", '["a","b"]')
    settings = NestedSettings()
    assert settings.tags == ["a", "b"]


def test_case_sensitive_env(monkeypatch) -> None:
    class CaseSettings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="FLB_", case_sensitive=True)
        MyField: str = "x"

    monkeypatch.setenv("FLB_MyField", "ok")
    assert CaseSettings().MyField == "ok"


def test_ignore_empty_env(monkeypatch) -> None:
    class EmptySettings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="FLB_", env_ignore_empty=True)
        name: str = "default"

    monkeypatch.setenv("FLB_NAME", "")
    assert EmptySettings().name == "default"


def test_parse_none_str(monkeypatch) -> None:
    class NoneSettings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="FLB_", env_parse_none_str="null")
        value: str | None = "fallback"

    monkeypatch.setenv("FLB_VALUE", "null")
    assert NoneSettings().value is None
