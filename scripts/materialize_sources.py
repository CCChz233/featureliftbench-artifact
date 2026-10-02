#!/usr/bin/env python3
"""Resolve, archive, and verify all canonical Full-Repository source trees."""

from __future__ import annotations

import argparse
import configparser
import gzip
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from featureliftbench.source_archive import (
    safe_extract_archive,
    sha256_file,
    tree_stats,
)


DEFAULT_REGISTRY = ROOT / "benchmark" / "sources" / "registry.json"
DEFAULT_ARCHIVE_DIR = ROOT / "benchmark" / "sources" / "archives"
EXACT_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
VERSION_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)+(?:[A-Za-z0-9.+-]*))")
LICENSE_NAMES = (
    "license",
    "license.txt",
    "license.md",
    "license.rst",
    "copying",
    "copying.txt",
    "notice",
    "notice.txt",
)
ACQUISITION_URL_OVERRIDES = {
    "source__sourceforge_net__a935d43b47a4": (
        "https://github.com/pycontribs/ruamel-yaml"
    ),
}
OFFICIAL_ARCHIVE_OVERRIDES = {
    (
        "https://foss.heptapod.net/python-libs/passlib",
        "1.7.4-installed-snapshot",
    ): {
        "archive_url": (
            "https://foss.heptapod.net/python-libs/passlib/-/archive/1.7.4/"
            "passlib-1.7.4.tar.gz"
        ),
        "resolved_commit": "45bd047ba3a37f43c39fd265f255c0721cf9233d",
        "revision_marker": ".hg_archival.txt",
        "revision_marker_text": (
            "node: 45bd047ba3a37f43c39fd265f255c0721cf9233d"
        ),
    },
}
RESOLUTION_COMMIT_OVERRIDES = {
    (
        "https://github.com/qlustered/deepdiff",
        "9.1.0-installed-snapshot",
    ): "c59636cda63cd3951777208c783285e6bf634159",
}
PINNED_SUBMODULES = {
    (
        "https://github.com/aio-libs/aiohttp",
        "649887ca860437e610fc4af5c8363a9be6f19681",
    ): (
        (
            "vendor/llhttp",
            "https://github.com/nodejs/llhttp",
            "01e105a30fd06e248bc8ac73c4adb34a63d4114a",
        ),
    ),
    (
        "https://github.com/python-poetry/tomlkit",
        "9ac3f98214dbfbca0157b6c370c7986f497c34e4",
    ): (
        (
            "tests/toml-test",
            "https://github.com/BurntSushi/toml-test",
            "08ed8697864548b3cdb4b8decbf496bef47e1c82",
        ),
    ),
}


@dataclass(frozen=True)
class MaterializationResult:
    snapshot_id: str
    evidence: dict[str, Any] | None
    error: str | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--snapshot-id", action="append", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="rebuild archives even when verified ready evidence already exists",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="finish other snapshots and record successful evidence after failures",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify existing ready archives without network or registry changes",
    )
    return parser.parse_args()


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 900,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_LFS_SKIP_SMUDGE": "1",
        },
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _version_from_requested(requested: str) -> str | None:
    for suffix in ("-installed-snapshot", "-curated-dag-snapshot"):
        if requested.endswith(suffix):
            requested = requested[: -len(suffix)]
    match = VERSION_RE.search(requested)
    return match.group(1) if match else None


def _github_slug(url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError(f"codeload acquisition requires a GitHub URL: {url}")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise ValueError(f"invalid GitHub repository URL: {url}")
    return parts[0], parts[1].removesuffix(".git")


def _urlopen(
    url: str,
    *,
    method: str = "GET",
    timeout: int = 300,
) -> Any:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "FeatureLiftBench-source-materializer/2"},
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.0 + attempt)
    assert last_error is not None
    raise last_error


def _tag_candidates(repository_name: str, version: str) -> list[str]:
    raw = (
        version,
        f"v{version}",
        f"{repository_name}-{version}",
        f"release-{version}",
        f"release/{version}",
        f"rel-{version}",
        f"rel/{version}",
    )
    return list(dict.fromkeys(raw))


def _resolve_version_tag(url: str, requested: str) -> tuple[str, str]:
    version = _version_from_requested(requested)
    if not version:
        raise ValueError(f"cannot derive a release version from {requested!r}")
    owner, repository = _github_slug(url)
    tag: str | None = None
    for candidate in _tag_candidates(repository, version):
        probe = (
            f"https://codeload.github.com/{owner}/{repository}/tar.gz/"
            f"{urllib.parse.quote(candidate, safe='')}"
        )
        try:
            with _urlopen(probe, method="HEAD", timeout=60) as response:
                if response.status == 200:
                    tag = candidate
                    break
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
    if tag is None:
        raise ValueError(f"no upstream tag matching version {version!r} for {url}")
    feed = (
        f"https://github.com/{owner}/{repository}/commits/"
        f"{urllib.parse.quote(tag, safe='')}.atom"
    )
    with _urlopen(feed, timeout=60) as response:
        text = response.read().decode("utf-8", errors="replace")
    match = re.search(r"Grit::Commit/([0-9a-fA-F]{40})", text)
    if not match:
        raise ValueError(f"cannot resolve tag {tag!r} to a commit via {feed}")
    return tag, match.group(1).lower()


def _download_codeload_tree(
    *,
    url: str,
    resolved_commit: str,
    destination: Path,
) -> None:
    owner, repository = _github_slug(url)
    archive_url = (
        f"https://codeload.github.com/{owner}/{repository}/tar.gz/"
        f"{resolved_commit}"
    )
    download = destination.parent / "upstream.tar.gz"
    with _urlopen(archive_url, timeout=1200) as response, download.open("wb") as out:
        shutil.copyfileobj(response, out, length=1024 * 1024)
    unpacked = destination.parent / "unpacked"
    safe_extract_archive(download, unpacked)
    children = list(unpacked.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise ValueError(
            f"unexpected codeload archive layout for {url}@{resolved_commit}"
        )
    wrapper = children[0]
    expected_suffix = f"-{resolved_commit}"
    if not wrapper.name.endswith(expected_suffix):
        raise ValueError(
            f"codeload archive root does not prove the requested commit: "
            f"{wrapper.name}"
        )
    wrapper.rename(destination)
    unpacked.rmdir()
    download.unlink()
    gitmodules = destination / ".gitmodules"
    if gitmodules.is_file():
        key = (url.removesuffix(".git").rstrip("/"), resolved_commit)
        submodules = PINNED_SUBMODULES.get(key) or _discover_submodules(
            url=url,
            resolved_commit=resolved_commit,
            gitmodules=gitmodules,
        )
        if not submodules:
            raise ValueError(
                "repository uses Git submodules but no audited gitlink map is "
                f"registered for {key[0]}@{resolved_commit}"
            )
        for relative, submodule_url, submodule_commit in submodules:
            submodule_path = destination / relative
            if submodule_path.exists() or submodule_path.is_symlink():
                if submodule_path.is_dir() and not submodule_path.is_symlink():
                    shutil.rmtree(submodule_path)
                else:
                    submodule_path.unlink()
            submodule_path.parent.mkdir(parents=True, exist_ok=True)
            _download_codeload_tree(
                url=submodule_url,
                resolved_commit=submodule_commit,
                destination=submodule_path,
            )
    elif PINNED_SUBMODULES.get(
        (url.removesuffix(".git").rstrip("/"), resolved_commit)
    ):
        raise ValueError(
            "audited submodule map exists but .gitmodules is absent from source"
        )


def _download_official_archive_tree(
    *,
    archive_url: str,
    destination: Path,
    revision_marker: str,
    revision_marker_text: str,
) -> None:
    download = destination.parent / "upstream.tar.gz"
    with _urlopen(archive_url, timeout=1200) as response, download.open("wb") as out:
        shutil.copyfileobj(response, out, length=1024 * 1024)
    unpacked = destination.parent / "unpacked"
    safe_extract_archive(download, unpacked)
    children = list(unpacked.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise ValueError(
            f"unexpected official archive layout: {archive_url}"
        )
    wrapper = children[0]
    marker = wrapper / revision_marker
    if (
        not marker.is_file()
        or revision_marker_text
        not in marker.read_text(encoding="utf-8", errors="replace")
    ):
        raise ValueError(
            f"official archive does not prove revision: {archive_url}"
        )
    wrapper.rename(destination)
    unpacked.rmdir()
    download.unlink()


def _discover_submodules(
    *,
    url: str,
    resolved_commit: str,
    gitmodules: Path,
) -> tuple[tuple[str, str, str], ...]:
    owner, repository = _github_slug(url)
    tree_url = (
        f"https://api.github.com/repos/{owner}/{repository}/git/trees/"
        f"{resolved_commit}?recursive=1"
    )
    with _urlopen(tree_url, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    gitlinks = {
        str(item["path"]): str(item["sha"])
        for item in payload.get("tree", [])
        if isinstance(item, dict) and item.get("type") == "commit"
    }
    parser = configparser.ConfigParser()
    parser.read_string(gitmodules.read_text(encoding="utf-8"))
    result: list[tuple[str, str, str]] = []
    for section in parser.sections():
        path = parser.get(section, "path")
        raw_url = parser.get(section, "url")
        if raw_url.startswith("../"):
            submodule_url = (
                f"https://github.com/{owner}/"
                f"{raw_url.removeprefix('../').removesuffix('.git')}"
            )
        else:
            submodule_url = raw_url.removesuffix(".git")
        commit = gitlinks.get(path)
        if not commit or not EXACT_COMMIT_RE.fullmatch(commit):
            raise ValueError(
                f"cannot resolve submodule gitlink {path!r} at {resolved_commit}"
            )
        result.append((path, submodule_url, commit.lower()))
    if not result:
        raise ValueError(".gitmodules exists but contains no resolvable submodules")
    if set(gitlinks) != {item[0] for item in result}:
        raise ValueError(
            "GitHub gitlinks and .gitmodules paths differ: "
            f"{sorted(gitlinks)} vs {sorted(item[0] for item in result)}"
        )
    return tuple(result)


def _checkout_git_tree(
    *,
    url: str,
    requested_revision: str,
    revision_kind: str,
    destination: Path,
) -> tuple[str, str]:
    if revision_kind == "git_commit":
        if not EXACT_COMMIT_RE.fullmatch(requested_revision):
            raise ValueError(f"invalid exact commit: {requested_revision}")
        fetch_revision = requested_revision
        resolution_ref = requested_revision
    else:
        overridden = RESOLUTION_COMMIT_OVERRIDES.get(
            (url.removesuffix(".git").rstrip("/"), requested_revision)
        )
        if overridden:
            resolution_ref = "verified_version_file_history"
            fetch_revision = overridden
        else:
            resolution_ref, fetch_revision = _resolve_version_tag(
                url, requested_revision
            )

    resolved = fetch_revision.lower()
    if not EXACT_COMMIT_RE.fullmatch(resolved):
        raise ValueError(f"resolved revision is not an exact commit: {resolved}")
    if revision_kind == "git_commit" and resolved != requested_revision.lower():
        raise ValueError(
            f"resolved commit mismatch: {resolved} != {requested_revision.lower()}"
        )
    _download_codeload_tree(
        url=url,
        resolved_commit=resolved,
        destination=destination,
    )
    return resolved, resolution_ref


def _remove_git_metadata(root: Path) -> None:
    candidates = sorted(
        (
            path
            for path in root.rglob(".git")
            if path != root and (path.is_dir() or path.is_file())
        ),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    root_git = root / ".git"
    if root_git.exists() or root_git.is_symlink():
        candidates.append(root_git)
    for path in candidates:
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()


def _tree_entries(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().encode()):
        relative = path.relative_to(root)
        if ".git" in relative.parts:
            continue
        yield path


def _tar_info(path: Path, root: Path) -> tarfile.TarInfo:
    relative = path.relative_to(root).as_posix()
    info = tarfile.TarInfo(relative + ("/" if path.is_dir() else ""))
    status = path.lstat()
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.mode = stat.S_IMODE(status.st_mode)
    if path.is_symlink():
        info.type = tarfile.SYMTYPE
        info.linkname = os.readlink(path)
        info.size = 0
    elif path.is_dir():
        info.type = tarfile.DIRTYPE
        info.size = 0
    elif path.is_file():
        info.type = tarfile.REGTYPE
        info.size = status.st_size
    else:
        raise ValueError(f"unsupported source tree entry: {path}")
    return info


def _write_deterministic_archive(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with temporary.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=0,
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in _tree_entries(root):
                    info = _tar_info(path, root)
                    if info.isfile():
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
                    else:
                        archive.addfile(info)
    temporary.replace(output)


def _find_license(root: Path) -> str:
    candidates: list[Path] = []
    for path in _tree_entries(root):
        if not (path.is_file() or path.is_symlink()):
            continue
        lowered = path.name.lower()
        if any(token in lowered for token in ("license", "copying", "notice")):
            candidates.append(path)
    if not candidates:
        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            try:
                project = tomllib.loads(
                    pyproject.read_text(encoding="utf-8")
                ).get("project")
            except (OSError, tomllib.TOMLDecodeError):
                project = None
            if isinstance(project, dict) and project.get("license"):
                return "pyproject.toml"
        raise ValueError(
            "no tracked LICENSE/COPYING/NOTICE or pyproject license evidence found"
        )
    selected = sorted(
        candidates,
        key=lambda path: (
            len(path.relative_to(root).parts),
            len(path.name),
            path.as_posix(),
        ),
    )[0]
    return selected.relative_to(root).as_posix()


def _verified_ready_archive(
    snapshot: dict[str, Any],
    archive_dir: Path,
) -> bool:
    raw = snapshot.get("archive_path")
    expected = snapshot.get("archive_sha256")
    if snapshot.get("status") != "ready" or not raw or not expected:
        return False
    archive = Path(str(raw))
    if not archive.is_absolute():
        archive = ROOT / archive
    return archive.is_file() and sha256_file(archive) == expected


def _materialize_one(
    snapshot: dict[str, Any],
    repository: dict[str, Any],
    archive_dir: Path,
    *,
    refresh: bool,
) -> MaterializationResult:
    snapshot_id = str(snapshot["source_snapshot_id"])
    try:
        if not refresh and _verified_ready_archive(snapshot, archive_dir):
            return MaterializationResult(snapshot_id, dict(snapshot), None)
        with tempfile.TemporaryDirectory(
            prefix=f"flb-source-{snapshot_id[:40]}-"
        ) as temporary:
            tree = Path(temporary) / "tree"
            if repository.get("source_kind") == "curated":
                relative_source = Path(str(repository["canonical_url"]))
                source = (
                    ROOT / "benchmark" / relative_source
                    if relative_source.parts
                    and relative_source.parts[0] == "sources"
                    else ROOT / relative_source
                )
                if not source.is_dir():
                    raise FileNotFoundError(f"curated source is missing: {source}")
                shutil.copytree(
                    source,
                    tree,
                    symlinks=True,
                    ignore=shutil.ignore_patterns(
                        ".git",
                        "__pycache__",
                        "*.pyc",
                        ".pytest_cache",
                        ".mypy_cache",
                        ".ruff_cache",
                    ),
                )
                resolved_commit = None
                resolution_ref = "curated"
                acquisition_method = "local_curated"
                target_scope = "curated_source_tree"
            else:
                url = ACQUISITION_URL_OVERRIDES.get(
                    str(repository["source_repo_id"]),
                    str(repository["canonical_url"]),
                )
                official = OFFICIAL_ARCHIVE_OVERRIDES.get(
                    (
                        str(repository["canonical_url"]),
                        str(snapshot["requested_revision"]),
                    )
                )
                if official:
                    resolved_commit = str(official["resolved_commit"])
                    resolution_ref = str(snapshot["requested_revision"])
                    _download_official_archive_tree(
                        archive_url=str(official["archive_url"]),
                        destination=tree,
                        revision_marker=str(official["revision_marker"]),
                        revision_marker_text=str(
                            official["revision_marker_text"]
                        ),
                    )
                    acquisition_method = "official_vcs_archive"
                else:
                    resolved_commit, resolution_ref = _checkout_git_tree(
                        url=url,
                        requested_revision=str(snapshot["requested_revision"]),
                        revision_kind=str(snapshot["revision_kind"]),
                        destination=tree,
                    )
                    acquisition_method = "git_checkout"
                target_scope = "full_tracked_tree"

            stats = tree_stats(tree)
            license_path = _find_license(tree)
            filename = (
                f"{snapshot_id}--{stats.source_tree_sha256[:16]}.tar.gz"
            )
            archive = archive_dir / filename
            _write_deterministic_archive(tree, archive)
            archive_sha = sha256_file(archive)
            relative_archive = archive.resolve().relative_to(ROOT).as_posix()
            evidence = {
                **snapshot,
                "resolved_commit": resolved_commit,
                "acquisition_method": acquisition_method,
                "current_snapshot_scope": target_scope,
                "status": "ready",
                "archive_path": relative_archive,
                "archive_sha256": archive_sha,
                "source_tree_sha256": stats.source_tree_sha256,
                "license_text_path": license_path,
                "tracked_file_count": stats.tracked_file_count,
                "python_file_count": stats.python_file_count,
                "python_loc": stats.python_loc,
                "total_bytes": stats.total_bytes,
                "max_path_depth": stats.max_path_depth,
            }
            del resolution_ref
            return MaterializationResult(snapshot_id, evidence, None)
    except Exception as exc:
        return MaterializationResult(
            snapshot_id,
            None,
            f"{type(exc).__name__}: {exc}",
        )


def _selected_snapshots(
    registry: dict[str, Any],
    *,
    task_ids: set[str],
    snapshot_ids: set[str],
) -> list[dict[str, Any]]:
    selected = []
    for snapshot in registry["snapshots"]:
        if snapshot_ids and snapshot["source_snapshot_id"] not in snapshot_ids:
            continue
        if task_ids and not task_ids.intersection(snapshot["task_ids"]):
            continue
        selected.append(snapshot)
    unknown_tasks = task_ids - {
        task_id for item in registry["snapshots"] for task_id in item["task_ids"]
    }
    if unknown_tasks:
        raise ValueError(f"unknown task IDs: {sorted(unknown_tasks)}")
    unknown_snapshots = snapshot_ids - {
        item["source_snapshot_id"] for item in registry["snapshots"]
    }
    if unknown_snapshots:
        raise ValueError(f"unknown snapshot IDs: {sorted(unknown_snapshots)}")
    return selected


def _write_registry(path: Path, registry: dict[str, Any]) -> None:
    ready = sum(item["status"] == "ready" for item in registry["snapshots"])
    registry["summary"]["ready_snapshot_count"] = ready
    registry["summary"]["pending_snapshot_count"] = (
        len(registry["snapshots"]) - ready
    )
    path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _check_ready_archives(
    snapshots: list[dict[str, Any]],
    archive_dir: Path,
) -> list[str]:
    errors: list[str] = []
    for snapshot in snapshots:
        snapshot_id = snapshot["source_snapshot_id"]
        if snapshot.get("status") != "ready":
            errors.append(f"{snapshot_id}: status={snapshot.get('status')}")
            continue
        if not _verified_ready_archive(snapshot, archive_dir):
            errors.append(f"{snapshot_id}: archive missing or digest mismatch")
    return errors


def main() -> int:
    args = _parse_args()
    registry_path = args.registry.resolve()
    archive_dir = args.archive_dir.resolve()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    repositories = {
        item["source_repo_id"]: item for item in registry["repositories"]
    }
    snapshots = _selected_snapshots(
        registry,
        task_ids=set(args.task_id),
        snapshot_ids=set(args.snapshot_id),
    )
    if args.check:
        errors = _check_ready_archives(snapshots, archive_dir)
        if errors:
            print("source archive verification failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print(f"verified {len(snapshots)} canonical source archives")
        return 0

    archive_dir.mkdir(parents=True, exist_ok=True)
    results: list[MaterializationResult] = []
    workers = max(1, min(args.workers, len(snapshots) or 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _materialize_one,
                snapshot,
                repositories[snapshot["source_repo_id"]],
                archive_dir,
                refresh=args.refresh,
            ): snapshot["source_snapshot_id"]
            for snapshot in snapshots
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result.error:
                print(f"FAIL {result.snapshot_id}: {result.error}", flush=True)
            else:
                print(f"READY {result.snapshot_id}", flush=True)

    successful = {
        result.snapshot_id: result.evidence
        for result in results
        if result.evidence is not None
    }
    for index, snapshot in enumerate(registry["snapshots"]):
        evidence = successful.get(snapshot["source_snapshot_id"])
        if evidence is not None:
            registry["snapshots"][index] = evidence
    _write_registry(registry_path, registry)

    failures = [result for result in results if result.error]
    print(
        f"materialized {len(successful)}/{len(results)} selected snapshots; "
        f"registry ready={registry['summary']['ready_snapshot_count']}/"
        f"{registry['summary']['snapshot_count']}"
    )
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
