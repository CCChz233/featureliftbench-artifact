"""Deterministic hashing helpers used by RSG manifests and stores."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_tree_digest(files: Iterable[tuple[Path, bytes]], root: Path) -> str:
    digest = hashlib.sha256()
    for path, content in sorted(files, key=lambda item: item[0].relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def builder_implementation_digest() -> str:
    """Hash every source/query file that can change graph construction semantics."""

    package_root = Path(__file__).resolve().parent
    candidates = [
        package_root / "builder.py",
        package_root / "hashing.py",
        package_root / "manifest.py",
        package_root / "models.py",
    ]
    candidates.extend((package_root / "parsing").rglob("*.py"))
    candidates.extend((package_root / "languages").rglob("*.py"))
    candidates.extend((package_root / "languages").rglob("*.scm"))
    digest = hashlib.sha256()
    for path in sorted(set(candidates), key=lambda item: item.relative_to(package_root).as_posix()):
        relative = path.relative_to(package_root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()
