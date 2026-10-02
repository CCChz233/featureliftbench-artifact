"""Snapshot manifest construction and validation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .hashing import builder_implementation_digest, digest_json
from .models import BUILDER_VERSION, SNAPSHOT_SCHEMA_VERSION, GraphEdge, GraphNode


def build_manifest(
    *,
    source_label: str,
    source_tree_hash: str,
    file_count: int,
    parsed_file_count: int,
    language_counts: dict[str, int],
    parser_versions: dict[str, str],
    adapters: dict[str, dict[str, Any]],
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    parse_error_files: list[str],
) -> dict[str, Any]:
    builder_identity = build_builder_identity(
        parser_versions=parser_versions,
        adapters=adapters,
    )
    identity = {
        "source_tree_hash": source_tree_hash,
        "builder": builder_identity,
    }
    graph_payload = {
        "nodes": [node.to_dict() for node in nodes],
        "edges": [edge.to_dict() for edge in edges],
    }
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": digest_json(identity),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "label": source_label,
            "tree_hash": source_tree_hash,
            "file_count": file_count,
            "parsed_file_count": parsed_file_count,
        },
        "builder": builder_identity,
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "unresolved_edges": sum(edge.resolution == "unresolved" for edge in edges),
            "parse_error_files": len(parse_error_files),
            "languages": dict(sorted(language_counts.items())),
        },
        "parse_error_files": sorted(parse_error_files),
        "graph_hash": digest_json(graph_payload),
    }


def build_builder_identity(
    *,
    parser_versions: dict[str, str],
    adapters: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return the exact builder identity used by cache and manifest IDs."""

    return {
        "builder_version": BUILDER_VERSION,
        "implementation_hash": builder_implementation_digest(),
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "parser_versions": parser_versions,
        "adapters": adapters,
    }


def validate_manifest_shape(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {manifest.get('schema_version')!r}")
    for key in ("snapshot_id", "source", "builder", "counts", "graph_hash"):
        if key not in manifest:
            errors.append(f"manifest missing {key}")
    return errors
