"""Lazy, version-auditable Tree-sitter backend."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any


class GrammarUnavailableError(RuntimeError):
    pass


class TreeSitterBackend:
    GRAMMAR_MODULES = {
        "python": "tree_sitter_python",
        "go": "tree_sitter_go",
    }

    def __init__(self) -> None:
        try:
            from tree_sitter import Language, Parser, Query, QueryCursor
        except ImportError as exc:
            raise GrammarUnavailableError(
                "repository graph support requires `pip install -e '.[repo-graph]'`"
            ) from exc
        self._Language = Language
        self._Parser = Parser
        self._Query = Query
        self._QueryCursor = QueryCursor
        self._languages: dict[str, Any] = {}

    def language(self, name: str) -> Any:
        if name in self._languages:
            return self._languages[name]
        module_name = self.GRAMMAR_MODULES.get(name)
        if module_name is None:
            raise GrammarUnavailableError(f"no Tree-sitter grammar registered for {name!r}")
        try:
            module = import_module(module_name)
        except ImportError as exc:
            raise GrammarUnavailableError(
                f"missing {module_name}; install the repo-graph optional dependencies"
            ) from exc
        language = self._Language(module.language())
        self._languages[name] = language
        return language

    def parse(self, language: str, source: bytes, *, old_tree: Any | None = None) -> Any:
        parser = self._Parser(self.language(language))
        tree = parser.parse(source, old_tree) if old_tree is not None else parser.parse(source)
        if tree.root_node.has_error:
            # A partial tree is intentionally still useful; adapters expose the flag.
            return tree
        return tree

    def captures(self, language: str, query_source: str, root_node: Any) -> dict[str, list[Any]]:
        query = self._Query(self.language(language), query_source)
        return self._QueryCursor(query).captures(root_node)

    @staticmethod
    def changed_ranges(old_tree: Any, new_tree: Any) -> list[Any]:
        return list(old_tree.changed_ranges(new_tree))

    def grammar_info(self, name: str) -> dict[str, Any]:
        language = self.language(name)
        semantic = getattr(language, "semantic_version", None)
        return {
            "name": language.name,
            "abi_version": language.abi_version,
            "semantic_version": ".".join(str(part) for part in semantic) if semantic else None,
            "node_kind_count": language.node_kind_count,
            "field_count": language.field_count,
        }

    @staticmethod
    def versions() -> dict[str, str]:
        result: dict[str, str] = {}
        for distribution in ("tree-sitter", "tree-sitter-python", "tree-sitter-go"):
            try:
                result[distribution] = version(distribution)
            except PackageNotFoundError:
                result[distribution] = "unavailable"
        return result
