"""Language-neutral RSG intermediate representation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SNAPSHOT_SCHEMA_VERSION = "featureliftbench.repo_graph.snapshot.v1"
QUERY_SCHEMA_VERSION = "featureliftbench.repo_graph.query.v1"
BUILDER_VERSION = "rsg-tree-sitter-v1"

RESOLUTION_LEVELS = frozenset(
    {"exact", "probable", "candidate", "unresolved", "unresolved_dynamic"}
)


@dataclass(frozen=True)
class SourceSpan:
    """A repository-relative source location. Lines are one-based; columns are zero-based."""

    path: str
    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceSpan:
        return cls(**data)


@dataclass
class GraphNode:
    id: int
    stable_id: str
    kind: str
    name: str
    qualified_name: str
    language: str | None = None
    span: SourceSpan | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.span is None:
            payload.pop("span")
        if self.language is None:
            payload.pop("language")
        if not self.attributes:
            payload.pop("attributes")
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphNode:
        payload = dict(data)
        if payload.get("span") is not None:
            payload["span"] = SourceSpan.from_dict(payload["span"])
        return cls(**payload)


@dataclass
class GraphEdge:
    id: int
    source: int
    target: int | None
    kind: str
    resolution: str
    provenance: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.resolution not in RESOLUTION_LEVELS:
            raise ValueError(f"unknown resolution level: {self.resolution}")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.target is None:
            payload.pop("target")
        if not self.attributes:
            payload.pop("attributes")
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphEdge:
        payload = dict(data)
        payload.setdefault("target", None)
        return cls(**payload)


@dataclass
class GraphSnapshot:
    manifest: dict[str, Any]
    nodes: list[GraphNode]
    edges: list[GraphEdge]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


@dataclass
class NodeSpec:
    """Builder-stage node keyed by stable ID before compact IDs are assigned."""

    stable_id: str
    kind: str
    name: str
    qualified_name: str
    language: str | None = None
    span: SourceSpan | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeSpec:
    """Builder-stage edge whose target may remain an unresolved expression."""

    source_stable_id: str
    target_stable_id: str | None
    kind: str
    resolution: str
    provenance: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.resolution not in RESOLUTION_LEVELS:
            raise ValueError(f"unknown resolution level: {self.resolution}")


@dataclass
class ParsedFile:
    nodes: list[NodeSpec] = field(default_factory=list)
    edges: list[EdgeSpec] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
