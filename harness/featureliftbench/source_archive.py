"""Verified materialization of canonical Full-Repository source archives."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SOURCE_REGISTRY_ENV = "FEATURELIFTBENCH_SOURCE_REGISTRY"
SOURCE_CACHE_ENV = "FEATURELIFTBENCH_SOURCE_CACHE"
DEFAULT_SOURCE_REGISTRY = Path("benchmark/sources/registry.json")
DEFAULT_SOURCE_CACHE = Path("benchmark/sources/archives")


@dataclass(frozen=True)
class SourceTreeStats:
    source_tree_sha256: str
    tracked_file_count: int
    python_file_count: int
    python_loc: int
    total_bytes: int
    max_path_depth: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "source_tree_sha256": self.source_tree_sha256,
            "tracked_file_count": self.tracked_file_count,
            "python_file_count": self.python_file_count,
            "python_loc": self.python_loc,
            "total_bytes": self.total_bytes,
            "max_path_depth": self.max_path_depth,
        }


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def source_registry_path(root: str | Path | None = None) -> Path:
    configured = os.environ.get(SOURCE_REGISTRY_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(root).resolve() if root is not None else project_root()
    return (base / DEFAULT_SOURCE_REGISTRY).resolve()


def source_cache_path(root: str | Path | None = None) -> Path:
    configured = os.environ.get(SOURCE_CACHE_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(root).resolve() if root is not None else project_root()
    return (base / DEFAULT_SOURCE_CACHE).resolve()


def load_source_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = (
        Path(path).resolve() if path is not None else source_registry_path()
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"source registry must be a JSON object: {registry_path}")
    return payload


def source_indexes(
    registry: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    snapshots: dict[str, dict[str, Any]] = {}
    task_snapshots: dict[str, dict[str, Any]] = {}
    for raw in registry.get("snapshots", []):
        if not isinstance(raw, dict):
            continue
        snapshot_id = str(raw.get("source_snapshot_id") or "")
        if not snapshot_id:
            continue
        snapshots[snapshot_id] = raw
        for task_id in raw.get("task_ids", []):
            key = str(task_id)
            if key in task_snapshots:
                raise ValueError(f"task maps to multiple source snapshots: {key}")
            task_snapshots[key] = raw
    return snapshots, task_snapshots


def source_provenance_for_task(
    task_id: str,
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any] | None:
    registry = load_source_registry(registry_path)
    _, task_snapshots = source_indexes(registry)
    snapshot = task_snapshots.get(task_id)
    if snapshot is None:
        return None
    return {
        "policy_id": registry.get("policy_id"),
        "source_repo_id": snapshot.get("source_repo_id"),
        "source_snapshot_id": snapshot.get("source_snapshot_id"),
        "requested_revision": snapshot.get("requested_revision"),
        "resolved_commit": snapshot.get("resolved_commit"),
        "source_digest": snapshot.get("source_tree_sha256"),
        "archive_sha256": snapshot.get("archive_sha256"),
        "snapshot_scope": snapshot.get("current_snapshot_scope"),
        "status": snapshot.get("status"),
    }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_tree_paths(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().encode()):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        if path.is_symlink() or path.is_file():
            yield path


def _git_mode(path: Path) -> tuple[str, str, bytes]:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path).encode("utf-8", errors="surrogateescape")
        return "symlink", "120000", target
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"unsupported tracked-tree entry: {path}")
    mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
    return "file", mode, path.read_bytes()


def tree_stats(root: str | Path) -> SourceTreeStats:
    base = Path(root).resolve()
    digest = hashlib.sha256()
    file_count = 0
    python_file_count = 0
    python_loc = 0
    total_bytes = 0
    max_depth = 0
    for path in _iter_tree_paths(base):
        relative = path.relative_to(base).as_posix()
        relative.encode("utf-8")
        kind, mode, content = _git_mode(path)
        blob_sha = hashlib.sha256(content).hexdigest()
        record = (
            kind.encode()
            + b"\0"
            + mode.encode()
            + b"\0"
            + relative.encode("utf-8")
            + b"\0"
            + str(len(content)).encode()
            + b"\0"
            + blob_sha.encode()
            + b"\n"
        )
        digest.update(record)
        file_count += 1
        total_bytes += len(content)
        max_depth = max(max_depth, len(PurePosixPath(relative).parts))
        if kind == "file" and relative.endswith(".py"):
            python_file_count += 1
            for raw_line in content.decode("utf-8", errors="ignore").splitlines():
                stripped = raw_line.strip()
                if stripped and not stripped.startswith("#"):
                    python_loc += 1
    return SourceTreeStats(
        source_tree_sha256=digest.hexdigest(),
        tracked_file_count=file_count,
        python_file_count=python_file_count,
        python_loc=python_loc,
        total_bytes=total_bytes,
        max_path_depth=max_depth,
    )


def _validate_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if member.isdir() and member.name.rstrip("/") in {"", "."}:
        return
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe source archive member: {member.name}")
    if member.issym() or member.islnk():
        target = PurePosixPath(member.linkname)
        if target.is_absolute():
            raise ValueError(
                f"absolute link target in source archive: {member.name}"
            )
        combined = path.parent.joinpath(target)
        depth = 0
        for part in combined.parts:
            depth += -1 if part == ".." else 0 if part == "." else 1
            if depth < 0:
                raise ValueError(
                    f"escaping link target in source archive: {member.name}"
                )
    if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
        raise ValueError(f"unsupported source archive member: {member.name}")


def safe_extract_archive(archive: str | Path, destination: str | Path) -> None:
    archive_path = Path(archive).resolve()
    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{target.name}.extract-",
        dir=target.parent,
    ) as temporary:
        staging = Path(temporary) / "tree"
        staging.mkdir()
        with tarfile.open(archive_path, "r:gz") as handle:
            members = handle.getmembers()
            for member in members:
                _validate_member(member)
            handle.extractall(staging, members=members)
        if target.exists() or target.is_symlink():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink()
        staging.rename(target)


def _archive_path_for_snapshot(
    snapshot: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> Path:
    raw = snapshot.get("archive_path")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(
            f"{snapshot.get('source_snapshot_id')}: archive_path is missing"
        )
    path = Path(raw)
    if path.is_absolute():
        return path
    base = Path(root).resolve() if root is not None else project_root()
    return (base / path).resolve()


def materialize_snapshot(
    snapshot: dict[str, Any],
    destination: str | Path,
    *,
    root: str | Path | None = None,
) -> SourceTreeStats:
    snapshot_id = str(snapshot.get("source_snapshot_id") or "unknown")
    if snapshot.get("status") != "ready":
        raise ValueError(f"{snapshot_id}: source snapshot is not ready")
    archive = _archive_path_for_snapshot(snapshot, root=root)
    if not archive.is_file():
        raise FileNotFoundError(
            f"{snapshot_id}: canonical source archive is missing: {archive}; "
            "run scripts/materialize_full_sources.py"
        )
    actual_archive_sha = sha256_file(archive)
    expected_archive_sha = str(snapshot.get("archive_sha256") or "")
    if actual_archive_sha != expected_archive_sha:
        raise ValueError(
            f"{snapshot_id}: archive digest mismatch "
            f"({actual_archive_sha} != {expected_archive_sha})"
        )
    safe_extract_archive(archive, destination)
    stats = tree_stats(destination)
    expected_tree_sha = str(snapshot.get("source_tree_sha256") or "")
    if stats.source_tree_sha256 != expected_tree_sha:
        raise ValueError(
            f"{snapshot_id}: source tree digest mismatch "
            f"({stats.source_tree_sha256} != {expected_tree_sha})"
        )
    for field in (
        "tracked_file_count",
        "python_file_count",
        "python_loc",
        "total_bytes",
        "max_path_depth",
    ):
        if getattr(stats, field) != snapshot.get(field):
            raise ValueError(
                f"{snapshot_id}: {field} mismatch "
                f"({getattr(stats, field)} != {snapshot.get(field)})"
            )
    return stats


def materialize_task_source(
    task_id: str,
    destination: str | Path,
    *,
    registry_path: str | Path | None = None,
    root: str | Path | None = None,
    require_registered: bool = False,
) -> dict[str, Any] | None:
    registry = load_source_registry(registry_path)
    _, task_snapshots = source_indexes(registry)
    snapshot = task_snapshots.get(task_id)
    if snapshot is None:
        if require_registered:
            raise ValueError(f"{task_id}: no canonical source snapshot registered")
        return None
    if snapshot.get("status") != "ready":
        if require_registered:
            raise ValueError(
                f"{task_id}: canonical source snapshot is not ready "
                f"({snapshot.get('status')})"
            )
        return None
    materialize_snapshot(snapshot, destination, root=root)
    return source_provenance_for_task(task_id, registry_path=registry_path)
