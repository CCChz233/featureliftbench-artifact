"""Conservative Go repository-level symbol resolution."""

from __future__ import annotations

from dataclasses import replace

from ...models import EdgeSpec, NodeSpec
from ...parsing.base import LanguageResolver


class GoResolver(LanguageResolver):
    def resolve(self, edge: EdgeSpec, nodes: dict[str, NodeSpec]) -> EdgeSpec:
        if edge.kind == "IMPORTS_MODULE":
            imported = str(edge.attributes.get("target_module", ""))
            local_modules = [
                node
                for node in nodes.values()
                if node.language == "go"
                and node.kind == "module"
                and (node.qualified_name == imported or imported.endswith(node.name))
            ]
            if len(local_modules) == 1:
                return replace(edge, target_stable_id=local_modules[0].stable_id, resolution="exact")
            return edge
        if edge.kind not in {"CALLS", "INIT_TIME_CALL"} or edge.target_stable_id is not None:
            return edge
        expression = str(edge.attributes.get("target_expression", ""))
        simple = expression.rsplit(".", 1)[-1]
        module = str(edge.attributes.get("module", ""))
        candidates = [
            node
            for node in nodes.values()
            if node.language == "go"
            and node.kind in {"function", "method", "type", "interface", "interface_method"}
            and node.name == simple
        ]
        local = [node for node in candidates if node.attributes.get("module") == module]
        if len(local) == 1 and "." not in expression:
            # Without go/types, a local function value may shadow the package symbol.
            return replace(edge, target_stable_id=local[0].stable_id, resolution="probable")
        if len(candidates) == 1:
            return replace(edge, target_stable_id=candidates[0].stable_id, resolution="candidate")
        return edge
