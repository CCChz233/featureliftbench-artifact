"""Shared helpers for Tree-sitter language adapters."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..models import SourceSpan


def query_pack_hash(query_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(query_dir.glob("*.scm")):
        name = path.name.encode("utf-8")
        content = path.read_bytes()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def load_query(query_dir: Path, name: str) -> str:
    return (query_dir / name).read_text(encoding="utf-8")


def node_text(node: Any, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def source_span(node: Any, relative_path: str) -> SourceSpan:
    return SourceSpan(
        path=relative_path,
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        start_line=node.start_point[0] + 1,
        start_column=node.start_point[1],
        end_line=node.end_point[0] + 1,
        end_column=node.end_point[1],
    )


def node_key(node: Any) -> tuple[int, int, str]:
    return (node.start_byte, node.end_byte, node.type)


def nearest_ancestor(node: Any, accepted: set[tuple[int, int, str]]) -> tuple[int, int, str] | None:
    current = node.parent
    while current is not None:
        key = node_key(current)
        if key in accepted:
            return key
        current = current.parent
    return None


def first_string_literal(text: str) -> str | None:
    for quote in ('"', "'"):
        start = text.find(quote)
        if start < 0:
            continue
        end = text.find(quote, start + 1)
        if end > start + 1:
            return text[start + 1 : end]
    return None


def pathish_string_literal(text: str) -> str | None:
    """Prefer path-like string literals over encoding / mode kwargs."""

    literals: list[str] = []
    for quote in ('"', "'"):
        start = 0
        while True:
            begin = text.find(quote, start)
            if begin < 0:
                break
            end = text.find(quote, begin + 1)
            if end < 0:
                break
            literals.append(text[begin + 1 : end])
            start = end + 1
    if not literals:
        return None
    skipped = {"utf-8", "utf8", "ascii", "latin-1", "r", "rb", "rt", "w", "wb", "a"}
    for literal in literals:
        lowered = literal.casefold()
        if lowered in skipped:
            continue
        if any(token in literal for token in ("/", "\\", ".", "_")) or lowered.endswith(
            (".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".txt", ".py")
        ):
            return literal
    for literal in literals:
        if literal.casefold() not in skipped:
            return literal
    return None
