"""Conservative Python repository-level symbol resolution."""

from __future__ import annotations

from dataclasses import replace

from ...models import EdgeSpec, NodeSpec
from ...parsing.base import LanguageResolver


_EXPRESSION_RESOLVE_KINDS = frozenset(
    {
        "CALLS",
        "IMPORT_TIME_CALL",
        "INHERITS",
        "EXPORTS",
        "PROVIDES_MEMBER",
        "RETURNS_TYPE",
        "RAISES",
        "DEFAULT_DEFINED_BY",
        "REGISTERS",
    }
)


class PythonResolver(LanguageResolver):
    def resolve(self, edge: EdgeSpec, nodes: dict[str, NodeSpec]) -> EdgeSpec:
        if edge.kind == "IMPORTS_MODULE":
            target_module = str(edge.attributes.get("target_module", "")).lstrip(".")
            local_id = f"python:{target_module}:module"
            if local_id in nodes:
                return replace(edge, target_stable_id=local_id, resolution="exact")
            return edge
        if edge.kind == "READS_CONFIG" and edge.target_stable_id is not None:
            return edge
        if edge.kind == "RESOLVES_VIA":
            # Keep dynamic dispatch unresolved; Boundaries consume these cues.
            return edge
        if edge.kind not in _EXPRESSION_RESOLVE_KINDS or edge.target_stable_id is not None:
            return edge
        expression = str(edge.attributes.get("target_expression", ""))
        if not expression or any(char in expression for char in "[](){}"):
            return edge
        module = str(edge.attributes.get("module", ""))
        scope = str(edge.attributes.get("scope_qualified", ""))
        simple = expression.rsplit(".", 1)[-1]
        accepted_kinds = {"function", "method", "class", "global_state", "type"}
        if edge.kind in {"RETURNS_TYPE", "RAISES", "INHERITS"}:
            accepted_kinds = {"class", "type"}
        candidates = [
            node
            for node in nodes.values()
            if node.language == "python"
            and node.kind in accepted_kinds
            and node.name == simple
        ]
        same_module = [node for node in candidates if node.attributes.get("module") == module]
        if edge.kind == "EXPORTS":
            exact = [
                node
                for node in same_module
                if node.qualified_name == f"{module}.{simple}" or node.name == simple
            ]
            if len(exact) == 1:
                return replace(edge, target_stable_id=exact[0].stable_id, resolution="exact")
            if len(same_module) == 1:
                return replace(edge, target_stable_id=same_module[0].stable_id, resolution="probable")
            return edge
        if expression.startswith("self.") or expression.startswith("cls."):
            class_scope = scope.rsplit(".", 1)[0]
            exact = [node for node in same_module if node.qualified_name == f"{class_scope}.{simple}"]
            if len(exact) == 1:
                # Runtime subclassing and monkey patching can redirect self/cls dispatch.
                return replace(edge, target_stable_id=exact[0].stable_id, resolution="probable")
        exact = [node for node in same_module if node.qualified_name == f"{module}.{expression}"]
        if len(exact) == 1:
            # Tree-sitter does not prove Python name binding or rule out monkey patching.
            return replace(edge, target_stable_id=exact[0].stable_id, resolution="probable")
        if len(same_module) == 1 and "." not in expression:
            return replace(edge, target_stable_id=same_module[0].stable_id, resolution="probable")
        suffix = f".{expression}"
        suffix_matches = [node for node in candidates if node.qualified_name.endswith(suffix)]
        if len(suffix_matches) == 1:
            return replace(edge, target_stable_id=suffix_matches[0].stable_id, resolution="candidate")
        return edge
