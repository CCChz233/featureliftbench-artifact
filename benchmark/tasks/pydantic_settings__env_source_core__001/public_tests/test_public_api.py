from __future__ import annotations

import os

from pydantic import Field

from featurelifted import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLB_", env_nested_delimiter="__")
    port: int = 80
    debug: bool = False
    db: dict = Field(default_factory=dict)


def test_env_prefix_and_nested(monkeypatch) -> None:
    monkeypatch.setenv("FLB_PORT", "9000")
    monkeypatch.setenv("FLB_DEBUG", "true")
    monkeypatch.setenv("FLB_DB__HOST", "db.internal")
    settings = AppSettings()
    assert settings.port == 9000
    assert settings.debug is True
    assert settings.db == {"host": "db.internal"}
