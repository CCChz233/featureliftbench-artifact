"""Build the private, source-free capsule used by functional evaluation.

The functional container must never receive an entire task directory.  A task
directory contains the upstream snapshot, provenance registries, compactness
references, and oracle metadata that are useful to maintainers but irrelevant
to functional execution.  This module creates the explicit allowlisted view
that may cross the functional-container boundary.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .metadata import load_metadata


CAPSULE_SCHEMA_VERSION = "featureliftbench.evaluation_capsule.v1"
CAPSULE_ALLOWED_TOP_LEVEL = frozenset(
    {
        "capsule.json",
        "metadata.json",
        "requirements.lock",
        "public_tests",
        "hidden_tests",
        "evaluation",
    }
)


def build_evaluation_capsule(task_dir: str | Path, destination: str | Path) -> dict[str, Any]:
    """Create a deterministic functional-evaluation capsule.

    Only evaluator inputs needed for dependency installation, API import, and
    public/hidden behavioral tests are copied.  In particular, ``repo/``,
    source registries/archives, reference implementations, closure gold, and
    compactness registries are never copied.
    """

    task = Path(task_dir).resolve()
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=True)
    metadata = load_metadata(task).data
    task_id = str(metadata.get("task_id") or task.name)

    safe_metadata = _functional_metadata(metadata)
    (target / "metadata.json").write_text(
        json.dumps(safe_metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lock = task / "requirements.lock"
    if lock.is_file():
        shutil.copy2(lock, target / "requirements.lock")
    else:
        (target / "requirements.lock").write_text("", encoding="utf-8")

    tests = safe_metadata.get("tests", {})
    for key, default in (("public", "public_tests/"), ("hidden", "hidden_tests/")):
        relative = str(tests.get(key) or default).rstrip("/")
        source = (task / relative).resolve()
        if not source.is_dir() or not _is_relative_to(source, task):
            raise ValueError(f"{task_id}: invalid {key} tests path: {relative}")
        destination_tests = target / ("public_tests" if key == "public" else "hidden_tests")
        shutil.copytree(
            source,
            destination_tests,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                ".pytest_cache",
                "_runtime_*",
                "*.pyc",
                "*.pyo",
            ),
        )

    forbidden = task / "evaluation" / "forbidden_imports.txt"
    if forbidden.is_file():
        evaluation_dir = target / "evaluation"
        evaluation_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(forbidden, evaluation_dir / "forbidden_imports.txt")

    manifest = {
        "schema_version": CAPSULE_SCHEMA_VERSION,
        "task_id": task_id,
        "allowed_top_level": sorted(CAPSULE_ALLOWED_TOP_LEVEL),
        "forbidden_payload_classes": [
            "task_repo",
            "canonical_source_archive",
            "source_registry",
            "reference_solution",
            "oracle_metadata",
            "compactness_registry",
            "closure_gold",
        ],
    }
    (target / "capsule.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert_capsule_allowlist(target)
    manifest["digest"] = evaluation_capsule_digest(target)
    return manifest


def assert_capsule_allowlist(capsule_dir: str | Path) -> None:
    """Fail closed when a capsule contains any non-allowlisted top-level path."""

    capsule = Path(capsule_dir).resolve()
    actual = {path.name for path in capsule.iterdir()}
    unexpected = sorted(actual - CAPSULE_ALLOWED_TOP_LEVEL)
    if unexpected:
        raise ValueError(f"evaluation capsule contains forbidden entries: {unexpected}")
    for forbidden in (
        "repo",
        "reference_solution",
        "oracle",
        "sources",
        "archives",
        "registry.json",
        "compactness.json",
    ):
        if (capsule / forbidden).exists():
            raise ValueError(f"evaluation capsule contains forbidden path: {forbidden}")


def evaluation_capsule_digest(capsule_dir: str | Path) -> str:
    """Hash capsule file paths and bytes in stable lexical order."""

    capsule = Path(capsule_dir).resolve()
    digest = hashlib.sha256()
    for path in sorted(item for item in capsule.rglob("*") if item.is_file()):
        relative = path.relative_to(capsule).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _functional_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    environment = metadata.get("environment")
    output = metadata.get("output")
    tests = metadata.get("tests")
    source = metadata.get("source")
    source_name = source.get("name") if isinstance(source, dict) else ""
    return {
        "task_id": metadata.get("task_id"),
        "language": metadata.get("language", "python"),
        "source": {"name": source_name},
        "output": output if isinstance(output, dict) else {},
        "environment": environment if isinstance(environment, dict) else {},
        "tests": {
            "command": tests.get("command", "pytest") if isinstance(tests, dict) else "pytest",
            "public": "public_tests/",
            "hidden": "hidden_tests/",
        },
        "capsule_schema_version": CAPSULE_SCHEMA_VERSION,
    }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
