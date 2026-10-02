"""Language adapter registration without hard-coding languages in the builder."""

from __future__ import annotations

from pathlib import Path

from .base import LanguageAdapter


class LanguageRegistry:
    def __init__(self) -> None:
        self._by_language: dict[str, LanguageAdapter] = {}
        self._by_extension: dict[str, LanguageAdapter] = {}

    def register(self, adapter: LanguageAdapter) -> None:
        if adapter.language in self._by_language:
            raise ValueError(f"duplicate language adapter: {adapter.language}")
        self._by_language[adapter.language] = adapter
        for extension in adapter.extensions:
            if extension in self._by_extension:
                raise ValueError(f"duplicate source extension: {extension}")
            self._by_extension[extension] = adapter

    def for_path(self, path: Path) -> LanguageAdapter | None:
        return self._by_extension.get(path.suffix.lower())

    def get(self, language: str) -> LanguageAdapter:
        try:
            return self._by_language[language]
        except KeyError as exc:
            raise ValueError(f"unsupported language: {language}") from exc

    def adapters(self) -> tuple[LanguageAdapter, ...]:
        return tuple(self._by_language[key] for key in sorted(self._by_language))

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset(self._by_extension)


def default_registry() -> LanguageRegistry:
    from ..languages.go import GoAdapter
    from ..languages.python import PythonAdapter

    registry = LanguageRegistry()
    registry.register(PythonAdapter())
    registry.register(GoAdapter())
    return registry
