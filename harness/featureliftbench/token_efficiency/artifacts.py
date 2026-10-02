"""Content-addressed hashing of evaluator-consumed submission trees."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .constants import IGNORE_NAME_PARTS, IGNORE_SUFFIXES


@dataclass(frozen=True)
class ArtifactEntry:
    relpath: str
    kind: str
    mode: str
    payload: bytes


def should_ignore(relpath: str) -> bool:
    parts = relpath.replace("\\", "/").split("/")
    if any(part in IGNORE_NAME_PARTS for part in parts):
        return True
    return any(part.endswith(IGNORE_SUFFIXES) for part in parts)


def iter_artifact_entries(root: Path) -> list[ArtifactEntry]:
    if not root.exists():
        return []
    entries: list[ArtifactEntry] = []
    seen_dirs = {""}
    try:
        paths = sorted(root.rglob("*"), key=lambda item: item.as_posix().replace("\x00", "").encode())
    except (OSError, ValueError):
        paths = list(root.rglob("*"))
    for path in paths:
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if "\x00" in rel or should_ignore(rel):
            continue
        parent = str(Path(rel).parent).replace("\\", "/")
        if parent == ".":
            parent = ""
        if parent and parent not in seen_dirs and not should_ignore(parent):
            entries.append(ArtifactEntry(parent, "dir", "040000", b""))
            seen_dirs.add(parent)
        if path.is_symlink():
            target = os.readlink(path).encode("utf-8", errors="surrogateescape")
            entries.append(ArtifactEntry(rel, "symlink", "120000", target))
            continue
        if path.is_dir():
            if rel not in seen_dirs:
                entries.append(ArtifactEntry(rel, "dir", "040000", b""))
                seen_dirs.add(rel)
            continue
        if not path.is_file():
            continue
        try:
            mode = "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"
            payload = path.read_bytes()
        except (OSError, ValueError):
            continue
        entries.append(ArtifactEntry(rel, "file", mode, payload))
    entries.sort(key=lambda item: item.relpath.encode())
    return entries


def artifact_hash(entries: Iterable[ArtifactEntry]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.kind.encode())
        digest.update(b"\0")
        digest.update(entry.mode.encode())
        digest.update(b"\0")
        digest.update(entry.relpath.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(entry.payload)).encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(entry.payload).digest())
        digest.update(b"\n")
    return digest.hexdigest()


def hash_tree(root: Path) -> str:
    return artifact_hash(iter_artifact_entries(root))


def empty_artifact_hash() -> str:
    return artifact_hash([])


def write_entries(dest: Path, entries: Iterable[ArtifactEntry]) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        path = dest / entry.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        if entry.kind == "dir":
            path.mkdir(parents=True, exist_ok=True)
        elif entry.kind == "symlink":
            if path.exists() or path.is_symlink():
                path.unlink()
            path.symlink_to(os.fsdecode(entry.payload))
        else:
            path.write_bytes(entry.payload)
            if entry.mode == "100755":
                path.chmod(path.stat().st_mode | stat.S_IXUSR)


def archive_entries(archive_path: Path, entries: Iterable[ArtifactEntry]) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    listed = list(entries)
    with tempfile.TemporaryDirectory(prefix="flb-art-") as tmp:
        root = Path(tmp) / "submission"
        write_entries(root, listed)
        with tarfile.open(archive_path, "w:gz") as handle:
            handle.add(root, arcname="submission")


def extract_archive(archive_path: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as handle:
        handle.extractall(dest.parent)
    extracted = dest.parent / "submission"
    if extracted.resolve() != dest.resolve():
        if dest.exists():
            shutil.rmtree(dest)
        extracted.rename(dest)
