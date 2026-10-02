from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

REGISTRY: dict[str, Callable[[str], str]] = {}


class Error(Exception):
    pass


class PublicAPI:
    def run(self, mode: str = "default") -> str:
        handler = REGISTRY[mode]
        return handler(mode)

    def boom(self) -> None:
        raise Error("failed")


def build(value: int = 1) -> PublicAPI:
    return PublicAPI()


def register(name: str) -> Callable[[Callable[[str], str]], Callable[[str], str]]:
    def decorator(fn: Callable[[str], str]) -> Callable[[str], str]:
        REGISTRY[name] = fn
        return fn

    return decorator


@register("echo")
def echo(mode: str) -> str:
    return mode


def dispatch(mode: str) -> str:
    selected = REGISTRY[mode]
    return selected(mode)


def load_settings() -> dict:
    path = Path(__file__).with_name("settings.toml")
    return {"path": str(path), "raw": path.read_text(encoding="utf-8")}


def load_json_config() -> dict:
    with open("config.json", encoding="utf-8") as handle:
        return json.load(handle)
