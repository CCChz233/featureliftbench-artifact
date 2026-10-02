"""Tree-sitter parsing infrastructure."""

from .base import LanguageAdapter, LanguageCapability, LanguageResolver
from .registry import LanguageRegistry, default_registry
from .tree_sitter_backend import GrammarUnavailableError, TreeSitterBackend

__all__ = [
    "GrammarUnavailableError",
    "LanguageAdapter",
    "LanguageCapability",
    "LanguageRegistry",
    "LanguageResolver",
    "TreeSitterBackend",
    "default_registry",
]
