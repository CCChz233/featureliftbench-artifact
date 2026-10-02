"""Small in-memory adjacency and symbol index for benchmark-sized repositories."""

from __future__ import annotations

from collections import defaultdict

from ..models import GraphEdge, GraphNode, GraphSnapshot


class MemoryGraphIndex:
    def __init__(self, snapshot: GraphSnapshot) -> None:
        self.snapshot = snapshot
        self.nodes_by_id = {node.id: node for node in snapshot.nodes}
        self.nodes_by_stable_id = {node.stable_id: node for node in snapshot.nodes}
        self.outgoing: dict[int, list[GraphEdge]] = defaultdict(list)
        self.incoming: dict[int, list[GraphEdge]] = defaultdict(list)
        self.symbols_by_name: dict[str, list[GraphNode]] = defaultdict(list)
        self.symbols_by_file: dict[str, list[GraphNode]] = defaultdict(list)
        for node in snapshot.nodes:
            self.symbols_by_name[node.name.casefold()].append(node)
            if node.span is not None:
                self.symbols_by_file[node.span.path].append(node)
        for edge in snapshot.edges:
            self.outgoing[edge.source].append(edge)
            if edge.target is not None:
                self.incoming[edge.target].append(edge)
        for edges in (*self.outgoing.values(), *self.incoming.values()):
            edges.sort(key=lambda edge: edge.id)
        for nodes in (*self.symbols_by_name.values(), *self.symbols_by_file.values()):
            nodes.sort(key=lambda node: (node.qualified_name, node.stable_id))

    def resolve_node(self, identifier: int | str) -> GraphNode | None:
        if isinstance(identifier, int):
            return self.nodes_by_id.get(identifier)
        if identifier.isdigit():
            return self.nodes_by_id.get(int(identifier))
        return self.nodes_by_stable_id.get(identifier)
