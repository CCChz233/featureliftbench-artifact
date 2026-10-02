from __future__ import annotations

import gzip
import io
import json
import os
import tarfile
from pathlib import Path
from unittest import mock

import pytest

from featureliftbench.source_archive import (
    materialize_task_source,
    safe_extract_archive,
    sha256_file,
    tree_stats,
)


def _archive_tree(source: Path, archive: Path) -> None:
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as handle:
                for path in sorted(source.rglob("*")):
                    handle.add(
                        path,
                        arcname=path.relative_to(source).as_posix(),
                        recursive=False,
                    )


def test_registered_archive_materializes_and_verifies(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    archive = tmp_path / "source.tar.gz"
    _archive_tree(source, archive)
    stats = tree_stats(source)
    registry = {
        "policy_id": "featureliftbench.full_repository_source.v1",
        "snapshots": [
            {
                "source_snapshot_id": "demo-snapshot",
                "source_repo_id": "demo-repo",
                "requested_revision": "a" * 40,
                "resolved_commit": "a" * 40,
                "status": "ready",
                "archive_path": str(archive),
                "archive_sha256": sha256_file(archive),
                **stats.as_dict(),
                "current_snapshot_scope": "full_tracked_tree",
                "task_ids": ["demo-task"],
            }
        ],
    }
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    destination = tmp_path / "workspace" / "repo"

    provenance = materialize_task_source(
        "demo-task",
        destination,
        registry_path=registry_path,
        require_registered=True,
    )

    assert provenance is not None
    assert provenance["source_digest"] == stats.source_tree_sha256
    assert (destination / "pkg" / "__init__.py").read_text() == "VALUE = 1\n"


def test_safe_extract_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        payload = b"escape"
        info = tarfile.TarInfo("../outside.txt")
        info.size = len(payload)
        handle.addfile(info, io.BytesIO(payload))

    with pytest.raises(ValueError, match="unsafe source archive member"):
        safe_extract_archive(archive, tmp_path / "target")

    assert not (tmp_path / "outside.txt").exists()


def test_safe_extract_allows_dot_root_directory(tmp_path: Path) -> None:
    archive = tmp_path / "rooted.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        root = tarfile.TarInfo("./")
        root.type = tarfile.DIRTYPE
        root.mode = 0o755
        handle.addfile(root)
        payload = b"value\n"
        info = tarfile.TarInfo("./value.txt")
        info.size = len(payload)
        info.mode = 0o644
        handle.addfile(info, io.BytesIO(payload))

    destination = tmp_path / "target"
    safe_extract_archive(archive, destination)

    assert (destination / "value.txt").read_bytes() == b"value\n"


def test_source_cache_environment_does_not_change_absolute_archive(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "LICENSE").write_text("demo\n", encoding="utf-8")
    archive = tmp_path / "source.tar.gz"
    _archive_tree(source, archive)
    stats = tree_stats(source)
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "snapshots": [
                    {
                        "source_snapshot_id": "demo",
                        "source_repo_id": "repo",
                        "status": "ready",
                        "archive_path": str(archive),
                        "archive_sha256": sha256_file(archive),
                        **stats.as_dict(),
                        "task_ids": ["task"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with mock.patch.dict(
        os.environ,
        {"FEATURELIFTBENCH_SOURCE_CACHE": str(tmp_path / "unused")},
    ):
        provenance = materialize_task_source(
            "task",
            tmp_path / "out",
            registry_path=registry_path,
            require_registered=True,
        )

    assert provenance is not None
