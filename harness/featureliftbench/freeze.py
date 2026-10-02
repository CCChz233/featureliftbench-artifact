"""Content-addressed manifests for evaluator and experiment freezes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


IGNORED_NAMES = {".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}
# Machine-local model/credential profiles (gitignored). These vary per experiment
# operator and must not be part of the benchmark freeze identity.
LOCAL_AGENT_CONFIG_NAMES = {"agents.toml", "agents.local.toml"}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_file() and not _ignored(path):
            files.append(path)
        elif path.is_dir():
            files.extend(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and not _ignored(candidate)
            )
    return sorted(set(candidate.resolve() for candidate in files))


def file_manifest(paths: Iterable[str | Path], *, root: str | Path) -> dict[str, str]:
    base = Path(root).resolve()
    result: dict[str, str] = {}
    for path in iter_files(paths):
        try:
            key = path.relative_to(base).as_posix()
        except ValueError as exc:
            raise ValueError(f"freeze path is outside root: {path} not under {base}") from exc
        result[key] = sha256_file(path)
    return dict(sorted(result.items()))


def manifest_digest(payload: dict) -> str:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    normalized.pop("freeze_id", None)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_file_manifest(
    expected: dict[str, str], *, root: str | Path
) -> list[dict[str, str]]:
    base = Path(root).resolve()
    mismatches: list[dict[str, str]] = []
    for relative, digest in sorted(expected.items()):
        # Tolerate legacy freezes that incorrectly pinned local agent configs.
        if Path(relative).name in LOCAL_AGENT_CONFIG_NAMES:
            continue
        path = base / relative
        if not path.is_file():
            mismatches.append({"path": relative, "expected": digest, "actual": "missing"})
            continue
        actual = sha256_file(path)
        if actual != digest:
            mismatches.append({"path": relative, "expected": digest, "actual": actual})
    return mismatches


def _ignored(path: Path) -> bool:
    return (
        path.name in IGNORED_NAMES
        or path.name in LOCAL_AGENT_CONFIG_NAMES
        or path.suffix in IGNORED_SUFFIXES
        or bool(set(path.parts) & IGNORED_PARTS)
    )
