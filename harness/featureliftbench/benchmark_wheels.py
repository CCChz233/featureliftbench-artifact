"""Load canonical benchmark wheel pin specs."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from .paths import CONFIG_DIR

BENCHMARK_WHEELS_TOML = CONFIG_DIR / "benchmark_wheels.toml"


@lru_cache(maxsize=1)
def load_benchmark_wheel_specs() -> dict[str, str]:
    if not BENCHMARK_WHEELS_TOML.is_file():
        return {}
    payload = tomllib.loads(BENCHMARK_WHEELS_TOML.read_text(encoding="utf-8"))
    specs: dict[str, str] = {}
    for section in ("sanity", "packages"):
        section_data = payload.get(section)
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                if isinstance(value, str) and value.strip():
                    specs[key.lower().replace("_", "-")] = value.strip()
    return specs


@lru_cache(maxsize=1)
def load_benchmark_wheel_aliases() -> dict[str, str]:
    if not BENCHMARK_WHEELS_TOML.is_file():
        return {}
    payload = tomllib.loads(BENCHMARK_WHEELS_TOML.read_text(encoding="utf-8"))
    aliases = payload.get("aliases")
    if not isinstance(aliases, dict):
        return {}
    return {
        str(key).lower().replace("_", "-"): str(value).lower().replace("_", "-")
        for key, value in aliases.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def resolve_wheel_spec(package_name: str) -> str | None:
    specs = load_benchmark_wheel_specs()
    aliases = load_benchmark_wheel_aliases()
    normalized = package_name.lower().replace("_", "-")
    resolved = aliases.get(normalized, normalized)
    return specs.get(resolved)


@lru_cache(maxsize=1)
def load_transitive_wheel_deps() -> dict[str, list[str]]:
    if not BENCHMARK_WHEELS_TOML.is_file():
        return {}
    payload = tomllib.loads(BENCHMARK_WHEELS_TOML.read_text(encoding="utf-8"))
    raw = payload.get("transitive")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, list):
            continue
        package = key.lower().replace("_", "-")
        deps = [
            str(item).lower().replace("_", "-")
            for item in value
            if isinstance(item, str) and str(item).strip()
        ]
        if deps:
            result[package] = deps
    return result


def expand_with_transitive_deps(package_names: list[str]) -> list[str]:
    transitive = load_transitive_wheel_deps()
    expanded: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        normalized = name.lower().replace("_", "-")
        if normalized in seen:
            return
        seen.add(normalized)
        expanded.append(normalized)
        for child in transitive.get(normalized, []):
            add(child)

    for name in package_names:
        add(name)
    return expanded


def all_benchmark_wheel_specs() -> list[str]:
    return sorted(set(load_benchmark_wheel_specs().values()), key=str.lower)


@lru_cache(maxsize=1)
def load_source_build_packages() -> set[str]:
    if not BENCHMARK_WHEELS_TOML.is_file():
        return set()
    payload = tomllib.loads(BENCHMARK_WHEELS_TOML.read_text(encoding="utf-8"))
    raw = payload.get("source_build")
    if not isinstance(raw, dict):
        return set()
    return {
        str(key).lower().replace("_", "-")
        for key, value in raw.items()
        if value is True
    }
