"""Bounded, deterministic RSG queries shared by CLI and future Agent adapters."""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable

from .models import GraphEdge, GraphNode, GraphSnapshot
from .storage import JsonlGraphStore, MemoryGraphIndex


DEPENDENCY_EDGE_KINDS = frozenset(
    {
        "CALLS",
        "DECORATED_BY",
        "DEFINES",
        "DEFAULT_DEFINED_BY",
        "DYNAMIC_GETATTR",
        "DYNAMIC_IMPORT",
        "EXPORTS",
        "IMPORTS_MODULE",
        "IMPORT_TIME_CALL",
        "INIT_TIME_CALL",
        "INHERITS",
        "LOADS_RESOURCE",
        "MUTABLE_GLOBAL",
        "MODULE_STATE",
        "PACKAGED_BY",
        "PROVIDES_MEMBER",
        "RAISES",
        "READS_CONFIG",
        "READS_CWD",
        "READS_ENV",
        "REGISTERS",
        "RESOLVES_VIA",
        "RETURNS_TYPE",
        "WRITES_CWD",
    }
)
DYNAMIC_RISK_EDGE_KINDS = frozenset(
    {
        "DYNAMIC_GETATTR",
        "DYNAMIC_IMPORT",
        "DYNAMIC_SETATTR",
        "IMPORT_TIME_CALL",
        "INIT_TIME_CALL",
        "LOADS_RESOURCE",
        "MUTABLE_GLOBAL",
        "MODULE_STATE",
        "PACKAGED_BY",
        "READS_CONFIG",
        "READS_CWD",
        "READS_ENV",
        "REGISTERS",
        "RESOLVES_VIA",
        "WRITES_CWD",
    }
)


class GraphQueryEngine:
    def __init__(self, snapshot: GraphSnapshot) -> None:
        self.snapshot = snapshot
        self.index = MemoryGraphIndex(snapshot)

    def search(
        self,
        query: str,
        *,
        kinds: Iterable[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        needle = query.strip().casefold()
        if not needle:
            raise ValueError("search query must not be empty")
        accepted = set(kinds) if kinds else None
        matches: list[tuple[int, GraphNode]] = []
        for node in self.snapshot.nodes:
            if accepted is not None and node.kind not in accepted:
                continue
            name = node.name.casefold()
            qualified = node.qualified_name.casefold()
            stable = node.stable_id.casefold()
            if needle == name:
                score = 100
            elif needle == qualified:
                score = 95
            elif qualified.endswith(f".{needle}"):
                score = 85
            elif needle in name:
                score = 70
            elif needle in qualified:
                score = 55
            elif needle in stable:
                score = 40
            else:
                continue
            matches.append((score, node))
        matches.sort(key=lambda item: (-item[0], item[1].qualified_name, item[1].stable_id))
        total = len(matches)
        start = max(0, offset)
        end = start + max(0, limit)
        return {
            "query": query,
            "total_matches": total,
            "matches": [
                {"score": score, **self._compact_node(node)} for score, node in matches[start:end]
            ],
            "truncated": end < total,
            "continuation_token": f"offset:{end}" if end < total else None,
        }

    def inspect(self, identifier: int | str, *, neighbor_limit: int = 30) -> dict[str, Any]:
        node = self.index.resolve_node(identifier)
        if node is None:
            raise ValueError(f"unknown node: {identifier}")
        edges = self.index.outgoing[node.id] + self.index.incoming[node.id]
        edges = sorted({edge.id: edge for edge in edges}.values(), key=lambda edge: edge.id)
        total = len(edges)
        return {
            "node": node.to_dict(),
            "neighbor_count": total,
            "neighbors": [self._edge_context(edge, node.id) for edge in edges[:neighbor_limit]],
            "truncated": total > neighbor_limit,
            "continuation_token": f"offset:{neighbor_limit}" if total > neighbor_limit else None,
        }

    def bootstrap(self, *, max_nodes: int = 30) -> dict[str, Any]:
        priority = {
            "repository": 0,
            "module": 1,
            "class": 2,
            "function": 3,
            "method": 4,
            "global_state": 5,
            "resource": 6,
            "environment_variable": 7,
            "dependency": 8,
            "file": 9,
        }
        ranked = sorted(
            self.snapshot.nodes,
            key=lambda node: (
                priority.get(node.kind, 50),
                -(len(self.index.outgoing[node.id]) + len(self.index.incoming[node.id])),
                node.qualified_name,
                node.stable_id,
            ),
        )
        selected = ranked[: max(0, max_nodes)]
        risks = self.risks(limit=10)
        return {
            "source": self.snapshot.manifest.get("source", {}),
            "counts": self.snapshot.manifest.get("counts", {}),
            "nodes": [self._compact_node(node) for node in selected],
            "dynamic_risk_summary": {
                "total": risks["total_risks"],
                "by_kind": risks["by_kind"],
            },
            "truncated": len(ranked) > len(selected),
            "continuation_token": f"offset:{len(selected)}" if len(ranked) > len(selected) else None,
        }

    def paths(
        self,
        source: int | str,
        target: int | str,
        *,
        max_depth: int = 4,
        max_paths: int = 5,
    ) -> dict[str, Any]:
        start = self.index.resolve_node(source)
        goal = self.index.resolve_node(target)
        if start is None or goal is None:
            raise ValueError("path source and target must identify existing nodes")
        queue: deque[tuple[int, list[int], list[int]]] = deque([(start.id, [start.id], [])])
        found: list[tuple[list[int], list[int]]] = []
        expansions = 0
        while queue and len(found) < max_paths and expansions < 10_000:
            current, node_path, edge_path = queue.popleft()
            if current == goal.id:
                found.append((node_path, edge_path))
                continue
            if len(edge_path) >= max_depth:
                continue
            for edge in self.index.outgoing[current]:
                if edge.target is None or edge.target in node_path:
                    continue
                queue.append((edge.target, node_path + [edge.target], edge_path + [edge.id]))
                expansions += 1
        if not found:
            return {"found": False, "source": start.stable_id, "target": goal.stable_id}
        return {
            "found": True,
            "paths": [
                {
                    "nodes": [
                        self._compact_node(self.index.nodes_by_id[node_id]) for node_id in node_ids
                    ],
                    "edges": [
                        self._compact_edge(self.snapshot.edges[edge_id - 1]) for edge_id in edge_ids
                    ],
                }
                for node_ids, edge_ids in found
            ],
            "search_truncated": bool(queue) or expansions >= 10_000,
        }

    def closure(
        self,
        entrypoints: Iterable[int | str],
        *,
        max_nodes: int = 100,
        include_candidates: bool = False,
    ) -> dict[str, Any]:
        roots: list[GraphNode] = []
        for identifier in entrypoints:
            node = self.index.resolve_node(identifier)
            if node is None:
                raise ValueError(f"unknown entrypoint: {identifier}")
            roots.append(node)
        if not roots:
            raise ValueError("at least one entrypoint is required")
        accepted_resolutions = {"exact", "probable"}
        if include_candidates:
            accepted_resolutions.add("candidate")
        queue: deque[int] = deque(node.id for node in roots)
        visited: set[int] = set()
        selected_edges: list[GraphEdge] = []
        unresolved: list[GraphEdge] = []
        while queue and len(visited) < max_nodes:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for edge in self.index.outgoing[current]:
                if edge.kind not in DEPENDENCY_EDGE_KINDS:
                    continue
                if edge.target is None or edge.resolution not in accepted_resolutions:
                    unresolved.append(edge)
                    continue
                selected_edges.append(edge)
                if edge.target not in visited:
                    queue.append(edge.target)
        nodes = [self.index.nodes_by_id[node_id] for node_id in sorted(visited)]
        return {
            "entrypoints": [node.stable_id for node in roots],
            "nodes": [self._compact_node(node) for node in nodes],
            "edges": [self._compact_edge(edge) for edge in selected_edges],
            "unresolved": [self._compact_edge(edge) for edge in unresolved[:50]],
            "truncated": bool(queue) or len(unresolved) > 50,
            "continuation_token": "closure:expand" if queue or len(unresolved) > 50 else None,
        }

    def risks(
        self,
        identifiers: Iterable[int | str] | None = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        selected_ids: set[int] | None = None
        if identifiers is not None:
            selected_ids = set()
            for identifier in identifiers:
                node = self.index.resolve_node(identifier)
                if node is None:
                    raise ValueError(f"unknown node: {identifier}")
                selected_ids.add(node.id)
        risks = [
            edge
            for edge in self.snapshot.edges
            if (edge.kind in DYNAMIC_RISK_EDGE_KINDS or edge.attributes.get("risk_category"))
            and (selected_ids is None or edge.source in selected_ids)
        ]
        by_kind: dict[str, int] = {}
        for edge in risks:
            by_kind[edge.kind] = by_kind.get(edge.kind, 0) + 1
        start = max(0, offset)
        end = start + max(0, limit)
        return {
            "total_risks": len(risks),
            "by_kind": dict(sorted(by_kind.items())),
            "risks": [self._edge_context(edge, edge.source) for edge in risks[start:end]],
            "truncated": end < len(risks),
            "continuation_token": f"offset:{end}" if end < len(risks) else None,
        }

    def self_check(self) -> dict[str, Any]:
        errors = JsonlGraphStore().check(self.snapshot)
        return {
            "valid": not errors,
            "errors": errors,
            "snapshot_id": self.snapshot.manifest.get("snapshot_id"),
            "counts": self.snapshot.manifest.get("counts", {}),
        }

    def _edge_context(self, edge: GraphEdge, focus_id: int) -> dict[str, Any]:
        source = self.index.nodes_by_id[edge.source]
        target = self.index.nodes_by_id.get(edge.target) if edge.target is not None else None
        other = target if edge.source == focus_id else source
        return {
            "edge": self._compact_edge(edge),
            "direction": "outgoing" if edge.source == focus_id else "incoming",
            "other": self._compact_node(other) if other is not None else None,
        }

    @staticmethod
    def _compact_node(node: GraphNode) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": node.id,
            "stable_id": node.stable_id,
            "kind": node.kind,
            "name": node.name,
            "qualified_name": node.qualified_name,
        }
        if node.language:
            result["language"] = node.language
        if node.span:
            result["location"] = f"{node.span.path}:{node.span.start_line}"
        return result

    @staticmethod
    def _compact_edge(edge: GraphEdge) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": edge.id,
            "source": edge.source,
            "kind": edge.kind,
            "resolution": edge.resolution,
        }
        if edge.target is not None:
            result["target"] = edge.target
        if edge.attributes:
            result["attributes"] = edge.attributes
        return result
