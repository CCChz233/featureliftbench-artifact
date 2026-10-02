from __future__ import annotations

import os
from pathlib import Path

REGISTRY: dict[str, object] = {}


class BaseService:
    pass


class Service(BaseService):
    def run(self, value: int) -> int:
        return helper(value)


def helper(value: int) -> int:
    return value + 1


def configuration() -> tuple[str | None, Path]:
    return os.getenv("FEATURE_MODE"), Path(__file__).with_name("schema.json")
