"""Interfaces implemented by language-specific adapters and resolvers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import EdgeSpec, NodeSpec, ParsedFile

if TYPE_CHECKING:
    from .tree_sitter_backend import TreeSitterBackend


@dataclass(frozen=True)
class LanguageCapability:
    language: str
    node_kinds: tuple[str, ...]
    edge_kinds: tuple[str, ...]
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class LanguageResolver(ABC):
    @abstractmethod
    def resolve(self, edge: EdgeSpec, nodes: dict[str, NodeSpec]) -> EdgeSpec:
        """Resolve a candidate edge against the complete repository symbol table."""


class LanguageAdapter(ABC):
    language: str
    extensions: tuple[str, ...]
    version: str
    capability: LanguageCapability

    @abstractmethod
    def parse(
        self,
        *,
        path: Path,
        relative_path: str,
        source: bytes,
        backend: TreeSitterBackend,
    ) -> ParsedFile:
        """Convert one source file into language-neutral node and edge specs."""

    @abstractmethod
    def query_pack_hash(self) -> str:
        """Return a digest of all query files used by this adapter."""

    @abstractmethod
    def resolver(self) -> LanguageResolver:
        """Return this language's repository-level resolver."""
