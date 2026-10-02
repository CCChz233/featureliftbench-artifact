"""Minimal Go Tree-sitter adapter proving the RSG IR is language-neutral."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ...models import EdgeSpec, NodeSpec, ParsedFile
from ...parsing.base import LanguageAdapter, LanguageCapability
from ...parsing.tree_sitter_backend import TreeSitterBackend
from ..common import load_query, nearest_ancestor, node_key, node_text, query_pack_hash, source_span
from .resolver import GoResolver


_IMPORT_RE = re.compile(r'(?m)(?:^|\s)(?:[\w.]+\s+)?"([^"]+)"')


class GoAdapter(LanguageAdapter):
    language = "go"
    extensions = (".go",)
    version = "go-adapter-v1"
    capability = LanguageCapability(
        language="go",
        node_kinds=(
            "dependency",
            "file",
            "function",
            "interface",
            "interface_method",
            "method",
            "module",
            "type",
        ),
        edge_kinds=("CALLS", "DEFINES", "IMPORTS_MODULE", "INIT_TIME_CALL"),
        limitations=("no go/packages", "no type checker", "interface dispatch is unresolved"),
    )

    def __init__(self) -> None:
        self.query_dir = Path(__file__).with_name("queries")

    def query_pack_hash(self) -> str:
        return query_pack_hash(self.query_dir)

    def resolver(self) -> GoResolver:
        return GoResolver()

    def parse(
        self,
        *,
        path: Path,
        relative_path: str,
        source: bytes,
        backend: TreeSitterBackend,
    ) -> ParsedFile:
        tree = backend.parse(self.language, source)
        root = tree.root_node
        symbol_captures = backend.captures(
            self.language,
            load_query(self.query_dir, "symbols.scm"),
            root,
        )
        package_nodes = symbol_captures.get("package.name", [])
        package = node_text(package_nodes[0], source) if package_nodes else Path(relative_path).parent.name
        directory = Path(relative_path).parent.as_posix()
        package_qualified = package if directory == "." else f"{directory.replace('/', '.')}.{package}"
        file_id = f"file:{relative_path}:file"
        package_id = f"go:{package_qualified}:module"
        parsed = ParsedFile(
            nodes=[
                NodeSpec(
                    file_id,
                    "file",
                    Path(relative_path).name,
                    relative_path,
                    self.language,
                    source_span(root, relative_path),
                    {"source_bytes": len(source), "parse_error": root.has_error},
                ),
                NodeSpec(
                    package_id,
                    "module",
                    package,
                    package_qualified,
                    self.language,
                    source_span(root, relative_path),
                    {"package": package, "directory": directory},
                ),
            ],
            edges=[EdgeSpec(file_id, package_id, "DEFINES", "exact", self.version)],
            metadata={"language": self.language, "module": package_qualified, "parse_error": root.has_error},
        )

        definitions: list[tuple[Any, str]] = []
        definitions.extend((node, "function") for node in symbol_captures.get("function.definition", []))
        definitions.extend((node, "method") for node in symbol_captures.get("method.definition", []))
        definitions.extend((node, "type") for node in symbol_captures.get("type.definition", []))
        definitions.extend(
            (node, "interface_method")
            for node in symbol_captures.get("interface_method.definition", [])
        )
        definitions.sort(key=lambda item: (item[0].start_byte, -item[0].end_byte, item[1]))
        definition_keys = {node_key(node) for node, _kind in definitions}
        stable_by_key: dict[tuple[int, int, str], str] = {}
        qualified_by_key: dict[tuple[int, int, str], str] = {}
        ordinal: defaultdict[str, int] = defaultdict(int)
        for definition, raw_kind in definitions:
            name_node = definition.child_by_field_name("name")
            if name_node is None and definition.type == "type_spec":
                name_node = definition.child_by_field_name("name")
            if name_node is None:
                continue
            name = node_text(name_node, source)
            kind = raw_kind
            parent_key = nearest_ancestor(definition, definition_keys)
            owner_id = stable_by_key.get(parent_key, package_id) if parent_key else package_id
            parent_qualified = qualified_by_key.get(parent_key) if parent_key else None
            if raw_kind == "type":
                type_node = definition.child_by_field_name("type")
                if type_node is not None and type_node.type == "interface_type":
                    kind = "interface"
            receiver_type = None
            if raw_kind == "method":
                receiver = definition.child_by_field_name("receiver")
                receiver_type = self._receiver_type(receiver, source) if receiver is not None else None
            if receiver_type:
                qualified = f"{package_qualified}.{receiver_type}.{name}"
            elif parent_qualified:
                qualified = f"{parent_qualified}.{name}"
            else:
                qualified = f"{package_qualified}.{name}"
            base_id = f"go:{qualified}:{kind}"
            definition_ordinal = ordinal[base_id]
            ordinal[base_id] += 1
            stable_id = base_id if definition_ordinal == 0 else f"{base_id}#{definition_ordinal}"
            parsed.nodes.append(
                NodeSpec(
                    stable_id,
                    kind,
                    name,
                    qualified,
                    self.language,
                    source_span(definition, relative_path),
                    {
                        "module": package_qualified,
                        "signature": node_text(definition, source).splitlines()[0].strip(),
                        "definition_ordinal": definition_ordinal,
                        **({"receiver_type": receiver_type} if receiver_type else {}),
                    },
                )
            )
            parsed.edges.append(EdgeSpec(owner_id, stable_id, "DEFINES", "exact", self.version))
            stable_by_key[node_key(definition)] = stable_id
            qualified_by_key[node_key(definition)] = qualified

        self._add_imports(parsed, backend, root, source, package_id, package_qualified)
        self._add_calls(
            parsed,
            backend,
            root,
            source,
            package_id,
            package_qualified,
            relative_path,
            definition_keys,
            stable_by_key,
        )
        return parsed

    @staticmethod
    def _receiver_type(receiver: Any, source: bytes) -> str | None:
        stack = [receiver]
        candidates: list[Any] = []
        while stack:
            current = stack.pop()
            if current.type == "type_identifier":
                candidates.append(current)
            stack.extend(reversed(current.named_children))
        return node_text(candidates[-1], source) if candidates else None

    def _add_imports(
        self,
        parsed: ParsedFile,
        backend: TreeSitterBackend,
        root: Any,
        source: bytes,
        package_id: str,
        package_qualified: str,
    ) -> None:
        captures = backend.captures(
            self.language,
            load_query(self.query_dir, "imports.scm"),
            root,
        )
        for import_spec in captures.get("import.spec", []):
            text = node_text(import_spec, source)
            match = _IMPORT_RE.search(text)
            if not match:
                continue
            imported = match.group(1)
            dependency_id = f"go:{imported}:dependency"
            parsed.nodes.append(
                NodeSpec(
                    dependency_id,
                    "dependency",
                    imported.rsplit("/", 1)[-1],
                    imported,
                    self.language,
                    attributes={"declared_by": package_qualified},
                )
            )
            parsed.edges.append(
                EdgeSpec(
                    package_id,
                    dependency_id,
                    "IMPORTS_MODULE",
                    "exact",
                    self.version,
                    {"target_module": imported, "statement": " ".join(text.split())},
                )
            )

    def _add_calls(
        self,
        parsed: ParsedFile,
        backend: TreeSitterBackend,
        root: Any,
        source: bytes,
        package_id: str,
        package_qualified: str,
        relative_path: str,
        definition_keys: set[tuple[int, int, str]],
        stable_by_key: dict[tuple[int, int, str], str],
    ) -> None:
        captures = backend.captures(
            self.language,
            load_query(self.query_dir, "calls.scm"),
            root,
        )
        for call in captures.get("call.expression", []):
            function = call.child_by_field_name("function")
            if function is None:
                continue
            expression = "".join(node_text(function, source).split())
            ancestor_key = nearest_ancestor(call, definition_keys)
            source_id = stable_by_key.get(ancestor_key, package_id)
            kind = "CALLS" if source_id != package_id else "INIT_TIME_CALL"
            parsed.edges.append(
                EdgeSpec(
                    source_id,
                    None,
                    kind,
                    "unresolved",
                    self.version,
                    {
                        "target_expression": expression[:300],
                        "module": package_qualified,
                        "path": relative_path,
                        "line": call.start_point[0] + 1,
                        **({"risk_category": "init_side_effect"} if source_id == package_id else {}),
                    },
                )
            )
