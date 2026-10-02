"""Deterministic multi-language RSG builder."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable

from .hashing import digest_json, source_tree_digest
from .manifest import build_builder_identity, build_manifest
from .models import EdgeSpec, GraphEdge, GraphNode, GraphSnapshot, NodeSpec
from .parsing import LanguageRegistry, TreeSitterBackend, default_registry


DEFAULT_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "node_modules",
        "venv",
    }
)


class GraphBuilder:
    def __init__(
        self,
        *,
        registry: LanguageRegistry | None = None,
        backend: TreeSitterBackend | None = None,
        ignored_directories: frozenset[str] = DEFAULT_IGNORED_DIRECTORIES,
    ) -> None:
        self.registry = registry or default_registry()
        self.backend = backend or TreeSitterBackend()
        self.ignored_directories = ignored_directories

    def build(
        self,
        repository: Path,
        *,
        languages: Iterable[str] | None = None,
    ) -> GraphSnapshot:
        root = repository.resolve()
        if not root.is_dir():
            raise ValueError(f"repository is not a directory: {repository}")
        allowed = set(languages) if languages is not None else None
        if allowed is not None:
            for language in allowed:
                self.registry.get(language)

        source_files: list[tuple[Path, bytes]] = []
        selected: list[tuple[Path, bytes, object]] = []
        for path in self._repository_paths(root):
            source = path.read_bytes()
            source_files.append((path, source))
            adapter = self.registry.for_path(path)
            if adapter is None or (allowed is not None and adapter.language not in allowed):
                continue
            selected.append((path, source, adapter))

        repository_id = "repository:root:repository"
        node_specs: dict[str, NodeSpec] = {
            repository_id: NodeSpec(
                repository_id,
                "repository",
                "repository",
                "repository",
            )
        }
        edge_specs: list[EdgeSpec] = []
        language_counts: Counter[str] = Counter()
        parse_error_files: list[str] = []
        used_languages: set[str] = set()

        for path, source, adapter_object in selected:
            adapter = adapter_object
            relative_path = path.relative_to(root).as_posix()
            parsed = adapter.parse(
                path=path,
                relative_path=relative_path,
                source=source,
                backend=self.backend,
            )
            language_counts[adapter.language] += 1
            used_languages.add(adapter.language)
            if parsed.metadata.get("parse_error"):
                parse_error_files.append(relative_path)
            for node in parsed.nodes:
                self._merge_node(node_specs, node)
            edge_specs.extend(parsed.edges)
            file_id = f"file:{relative_path}:file"
            edge_specs.append(
                EdgeSpec(repository_id, file_id, "CONTAINS", "exact", "graph-builder-v1")
            )

        for language in sorted(used_languages):
            resolver = self.registry.get(language).resolver()
            edge_specs = [
                resolver.resolve(edge, node_specs)
                if node_specs.get(edge.source_stable_id, NodeSpec("", "", "", "")).language
                == language
                else edge
                for edge in edge_specs
            ]

        from .packaging import add_packaging_edges

        add_packaging_edges(root, node_specs, edge_specs)

        nodes = self._materialize_nodes(node_specs)
        node_ids = {node.stable_id: node.id for node in nodes}
        edges = self._materialize_edges(edge_specs, node_ids)
        adapters = {
            language: {
                "adapter_version": self.registry.get(language).version,
                "query_pack_hash": self.registry.get(language).query_pack_hash(),
                "grammar": self.backend.grammar_info(language),
                "capability": self.registry.get(language).capability.to_dict(),
            }
            for language in sorted(used_languages)
        }
        manifest = build_manifest(
            source_label=root.name,
            source_tree_hash=source_tree_digest(source_files, root),
            file_count=len(source_files),
            parsed_file_count=len(selected),
            language_counts=dict(language_counts),
            parser_versions=self.backend.versions(),
            adapters=adapters,
            nodes=nodes,
            edges=edges,
            parse_error_files=parse_error_files,
        )
        return GraphSnapshot(manifest=manifest, nodes=nodes, edges=edges)

    def fingerprint(
        self,
        repository: Path,
        *,
        languages: Iterable[str] | None = None,
    ) -> dict[str, object]:
        """Compute the cache identity without parsing source files."""

        root = repository.resolve()
        if not root.is_dir():
            raise ValueError(f"repository is not a directory: {repository}")
        allowed = set(languages) if languages is not None else None
        if allowed is not None:
            for language in allowed:
                self.registry.get(language)
        source_files: list[tuple[Path, bytes]] = []
        parsed_file_count = 0
        language_counts: Counter[str] = Counter()
        used_languages: set[str] = set()
        for path in self._repository_paths(root):
            source = path.read_bytes()
            source_files.append((path, source))
            adapter = self.registry.for_path(path)
            if adapter is None or (allowed is not None and adapter.language not in allowed):
                continue
            parsed_file_count += 1
            language_counts[adapter.language] += 1
            used_languages.add(adapter.language)
        adapters = self._adapter_identity(used_languages)
        builder_identity = build_builder_identity(
            parser_versions=self.backend.versions(),
            adapters=adapters,
        )
        source_hash = source_tree_digest(source_files, root)
        snapshot_id = digest_json(
            {"source_tree_hash": source_hash, "builder": builder_identity}
        )
        return {
            "snapshot_id": snapshot_id,
            "source_tree_hash": source_hash,
            "source_label": root.name,
            "file_count": len(source_files),
            "parsed_file_count": parsed_file_count,
            "language_counts": dict(sorted(language_counts.items())),
            "builder": builder_identity,
        }

    def _adapter_identity(self, languages: Iterable[str]) -> dict[str, dict[str, object]]:
        return {
            language: {
                "adapter_version": self.registry.get(language).version,
                "query_pack_hash": self.registry.get(language).query_pack_hash(),
                "grammar": self.backend.grammar_info(language),
                "capability": self.registry.get(language).capability.to_dict(),
            }
            for language in sorted(languages)
        }

    def _repository_paths(self, root: Path) -> list[Path]:
        paths: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in self.ignored_directories for part in relative.parts[:-1]):
                continue
            if relative.parts and relative.parts[0] in {"build", "dist"}:
                continue
            paths.append(path)
        return sorted(paths, key=lambda path: path.relative_to(root).as_posix())

    @staticmethod
    def _merge_node(nodes: dict[str, NodeSpec], candidate: NodeSpec) -> None:
        existing = nodes.get(candidate.stable_id)
        if existing is None:
            nodes[candidate.stable_id] = candidate
            return
        if (existing.kind, existing.qualified_name, existing.language) != (
            candidate.kind,
            candidate.qualified_name,
            candidate.language,
        ):
            raise ValueError(f"stable ID collision: {candidate.stable_id}")
        existing.attributes.update(
            {key: value for key, value in candidate.attributes.items() if key not in existing.attributes}
        )

    @staticmethod
    def _materialize_nodes(specs: dict[str, NodeSpec]) -> list[GraphNode]:
        return [
            GraphNode(
                id=index,
                stable_id=spec.stable_id,
                kind=spec.kind,
                name=spec.name,
                qualified_name=spec.qualified_name,
                language=spec.language,
                span=spec.span,
                attributes=spec.attributes,
            )
            for index, spec in enumerate(
                sorted(specs.values(), key=lambda item: item.stable_id),
                start=1,
            )
        ]

    @staticmethod
    def _materialize_edges(specs: list[EdgeSpec], node_ids: dict[str, int]) -> list[GraphEdge]:
        materialized: list[GraphEdge] = []
        sorted_specs = sorted(
            specs,
            key=lambda edge: (
                edge.source_stable_id,
                edge.kind,
                edge.target_stable_id or "",
                edge.resolution,
                str(sorted(edge.attributes.items())),
            ),
        )
        for index, edge in enumerate(sorted_specs, start=1):
            if edge.source_stable_id not in node_ids:
                raise ValueError(f"edge source missing: {edge.source_stable_id}")
            target = node_ids.get(edge.target_stable_id) if edge.target_stable_id else None
            if edge.target_stable_id and target is None:
                raise ValueError(f"edge target missing: {edge.target_stable_id}")
            materialized.append(
                GraphEdge(
                    id=index,
                    source=node_ids[edge.source_stable_id],
                    target=target,
                    kind=edge.kind,
                    resolution=edge.resolution,
                    provenance=edge.provenance,
                    attributes=edge.attributes,
                )
            )
        return materialized
