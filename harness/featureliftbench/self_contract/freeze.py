"""Freeze helpers — compute manifest without clobbering lock during checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .common import CONTRACTS_DIR
from .common import LOCK_FILE
from .common import MANIFEST_FILE


def compute_contracts_manifest(workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    contracts = workspace / CONTRACTS_DIR
    files: dict[str, str] = {}
    if contracts.is_dir():
        for path in sorted(contracts.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            rel = path.relative_to(contracts).as_posix()
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {
        "schema_version": "featureliftbench.self_contract_manifest.v1",
        "files": files,
        "file_count": len(files),
    }
    lock = hashlib.sha256(
        json.dumps({"files": files}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    payload["lock"] = lock
    return payload


def freeze_contracts(workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    payload = compute_contracts_manifest(workspace)
    (workspace / MANIFEST_FILE).write_text(
        json.dumps(
            {k: v for k, v in payload.items() if k != "lock"},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / LOCK_FILE).write_text(str(payload["lock"]) + "\n", encoding="utf-8")
    return payload


def verify_contracts_frozen(workspace_dir: str | Path) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    lock_path = workspace / LOCK_FILE
    if not lock_path.is_file():
        return {"ok": False, "error": f"missing {LOCK_FILE}"}
    expected = lock_path.read_text(encoding="utf-8").strip()
    current = compute_contracts_manifest(workspace)
    if current.get("lock") != expected:
        return {
            "ok": False,
            "error": "contracts lock mismatch (contracts modified after freeze)",
            "expected_lock": expected,
            "actual_lock": current.get("lock"),
        }
    return {"ok": True, "lock": expected, "file_count": current.get("file_count")}
