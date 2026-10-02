"""Auditable JSONL snapshot persistence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from ..hashing import canonical_json, digest_json
from ..manifest import validate_manifest_shape
from ..models import GraphEdge, GraphNode, GraphSnapshot


class JsonlGraphStore:
    MANIFEST = "manifest.json"
    NODES = "nodes.jsonl"
    EDGES = "edges.jsonl"

    def write(self, snapshot: GraphSnapshot, output_dir: Path) -> Path:
        output = output_dir.resolve()
        output.mkdir(parents=True, exist_ok=True)
        node_text = self._jsonl(node.to_dict() for node in snapshot.nodes)
        edge_text = self._jsonl(edge.to_dict() for edge in snapshot.edges)
        snapshot.manifest["artifacts"] = {
            self.NODES: self._text_digest(node_text),
            self.EDGES: self._text_digest(edge_text),
        }
        self._atomic_write(output / self.NODES, node_text)
        self._atomic_write(output / self.EDGES, edge_text)
        self._atomic_write(
            output / self.MANIFEST,
            json.dumps(snapshot.manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        return output

    def load(self, input_dir: Path, *, verify: bool = True) -> GraphSnapshot:
        root = input_dir.resolve()
        manifest = json.loads((root / self.MANIFEST).read_text(encoding="utf-8"))
        nodes = [GraphNode.from_dict(row) for row in self._read_jsonl(root / self.NODES)]
        edges = [GraphEdge.from_dict(row) for row in self._read_jsonl(root / self.EDGES)]
        snapshot = GraphSnapshot(manifest=manifest, nodes=nodes, edges=edges)
        if verify:
            errors = self.check(snapshot, root)
            if errors:
                raise ValueError("invalid graph snapshot: " + "; ".join(errors))
        return snapshot

    def check(self, snapshot: GraphSnapshot, root: Path | None = None) -> list[str]:
        errors = validate_manifest_shape(snapshot.manifest)
        node_ids = {node.id for node in snapshot.nodes}
        stable_ids = {node.stable_id for node in snapshot.nodes}
        if len(node_ids) != len(snapshot.nodes):
            errors.append("duplicate compact node ID")
        if len(stable_ids) != len(snapshot.nodes):
            errors.append("duplicate stable node ID")
        for edge in snapshot.edges:
            if edge.source not in node_ids:
                errors.append(f"edge {edge.id} has missing source {edge.source}")
            if edge.target is not None and edge.target not in node_ids:
                errors.append(f"edge {edge.id} has missing target {edge.target}")
        graph_hash = digest_json(
            {
                "nodes": [node.to_dict() for node in snapshot.nodes],
                "edges": [edge.to_dict() for edge in snapshot.edges],
            }
        )
        if snapshot.manifest.get("graph_hash") != graph_hash:
            errors.append("graph_hash mismatch")
        counts = snapshot.manifest.get("counts", {})
        if counts.get("nodes") != len(snapshot.nodes):
            errors.append("manifest node count mismatch")
        if counts.get("edges") != len(snapshot.edges):
            errors.append("manifest edge count mismatch")
        if root is not None:
            for filename, expected in snapshot.manifest.get("artifacts", {}).items():
                path = root / filename
                if not path.is_file():
                    errors.append(f"missing artifact {filename}")
                elif self._text_digest(path.read_text(encoding="utf-8")) != expected:
                    errors.append(f"artifact hash mismatch: {filename}")
        return errors

    @staticmethod
    def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
        return "".join(canonical_json(row) + "\n" for row in rows)

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL {path.name}:{line_number}: {exc}") from exc
                if not isinstance(value, dict):
                    raise ValueError(f"invalid JSONL object {path.name}:{line_number}")
                rows.append(value)
        return rows

    @staticmethod
    def _text_digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
