"""Task constitution spec loading, hashing, and shape validation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SPEC_STATUS_LEGACY = "legacy"
SPEC_STATUS_COMPLIANT = "compliant"
SPEC_STATUSES = {SPEC_STATUS_LEGACY, SPEC_STATUS_COMPLIANT}

API_PATH_RE = re.compile(
    r"^featurelifted(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?:\.__[a-z_]+__)?$"
)


@dataclass(frozen=True)
class SpecHashes:
    spec_hash: str
    generated_task_hash: str


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_spec_status(metadata: dict[str, Any]) -> str:
    status = metadata.get("spec_status")
    if isinstance(status, str) and status in SPEC_STATUSES:
        return status
    if isinstance(metadata.get("public_spec"), dict):
        return SPEC_STATUS_COMPLIANT
    return SPEC_STATUS_LEGACY


def load_public_spec(metadata: dict[str, Any]) -> dict[str, Any] | None:
    public_spec = metadata.get("public_spec")
    return public_spec if isinstance(public_spec, dict) else None


def load_evaluation_spec(metadata: dict[str, Any]) -> dict[str, Any] | None:
    evaluation_spec = metadata.get("evaluation_spec")
    return evaluation_spec if isinstance(evaluation_spec, dict) else None


def compute_spec_hash(public_spec: dict[str, Any]) -> str:
    return sha256_text(canonical_json(public_spec))


def compute_generated_task_hash(task_markdown: str) -> str:
    return sha256_text(task_markdown)


def validate_api_entry(entry: Any, *, label: str, errors: list[str]) -> None:
    if not isinstance(entry, dict):
        errors.append(f"{label} must be an object")
        return
    path = entry.get("path")
    kind = entry.get("kind")
    if not isinstance(path, str) or not API_PATH_RE.match(path):
        errors.append(f"{label}.path must match featurelifted API path format: {path!r}")
    if not isinstance(kind, str) or not kind.strip():
        errors.append(f"{label}.kind must be a non-empty string")
    members = entry.get("members")
    if members is not None:
        if not isinstance(members, list):
            errors.append(f"{label}.members must be a list")
        else:
            for index, member in enumerate(members):
                validate_api_entry(member, label=f"{label}.members[{index}]", errors=errors)


def validate_behavior_entry(entry: Any, *, label: str, errors: list[str]) -> None:
    if not isinstance(entry, dict):
        errors.append(f"{label} must be an object")
        return
    behavior_id = entry.get("id")
    text = entry.get("text")
    if not isinstance(behavior_id, str) or not re.fullmatch(r"B\d{3,}", behavior_id):
        errors.append(f"{label}.id must look like B001: {behavior_id!r}")
    if not isinstance(text, str) or len(text.strip()) < 20:
        errors.append(f"{label}.text must be an observable behavior sentence")


def validate_public_spec_shape(public_spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("title", "summary"):
        if not isinstance(public_spec.get(key), str) or not str(public_spec.get(key)).strip():
            errors.append(f"public_spec.{key} must be a non-empty string")

    required_api = public_spec.get("required_api")
    if not isinstance(required_api, list) or not required_api:
        errors.append("public_spec.required_api must be a non-empty list")
    else:
        for index, entry in enumerate(required_api):
            validate_api_entry(entry, label=f"public_spec.required_api[{index}]", errors=errors)

    optional_api = public_spec.get("optional_api", [])
    if optional_api is None:
        optional_api = []
    if not isinstance(optional_api, list):
        errors.append("public_spec.optional_api must be a list")
    else:
        for index, entry in enumerate(optional_api):
            validate_api_entry(entry, label=f"public_spec.optional_api[{index}]", errors=errors)

    behaviors = public_spec.get("behaviors")
    if not isinstance(behaviors, list) or not behaviors:
        errors.append("public_spec.behaviors must be a non-empty list")
    else:
        ids: set[str] = set()
        for index, entry in enumerate(behaviors):
            validate_behavior_entry(entry, label=f"public_spec.behaviors[{index}]", errors=errors)
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                if entry["id"] in ids:
                    errors.append(f"duplicate behavior id: {entry['id']}")
                ids.add(entry["id"])

    exclusions = public_spec.get("exclusions")
    if not isinstance(exclusions, list):
        errors.append("public_spec.exclusions must be a list")

    forbidden = public_spec.get("forbidden")
    if not isinstance(forbidden, dict):
        errors.append("public_spec.forbidden must be an object")
    else:
        for key in ("imports", "paths"):
            value = forbidden.get(key)
            if not isinstance(value, list):
                errors.append(f"public_spec.forbidden.{key} must be a list")

    return errors


def validate_evaluation_spec_shape(evaluation_spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("public_test_mappings", "hidden_test_mappings", "public_clauses"):
        value = evaluation_spec.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"evaluation_spec.{key} must be a non-empty list")

    required_api_coverage = evaluation_spec.get("required_api_coverage")
    if not isinstance(required_api_coverage, list) or not required_api_coverage:
        errors.append("evaluation_spec.required_api_coverage must be a non-empty list")
    else:
        for index, entry in enumerate(required_api_coverage):
            if not isinstance(entry, dict):
                errors.append(f"evaluation_spec.required_api_coverage[{index}] must be an object")
                continue
            path = entry.get("path")
            tests = entry.get("covered_by_tests")
            if not isinstance(path, str):
                errors.append(
                    f"evaluation_spec.required_api_coverage[{index}].path must be a string"
                )
            if not isinstance(tests, list) or not tests:
                errors.append(
                    f"evaluation_spec.required_api_coverage[{index}].covered_by_tests must be non-empty"
                )

    manual_review = evaluation_spec.get("manual_review")
    if not isinstance(manual_review, dict):
        errors.append("evaluation_spec.manual_review must be an object")
    elif manual_review.get("checklist_passed") is not True:
        errors.append("evaluation_spec.manual_review.checklist_passed must be true for compliant tasks")

    return errors


def sync_spec_hashes(metadata: dict[str, Any], task_markdown: str) -> dict[str, Any]:
    """Return metadata copy with spec_hash and generated_task_hash updated."""

    public_spec = load_public_spec(metadata)
    if public_spec is None:
        return dict(metadata)
    updated = dict(metadata)
    updated["spec_hash"] = compute_spec_hash(public_spec)
    updated["generated_task_hash"] = compute_generated_task_hash(task_markdown)
    if "task_revision" not in updated:
        updated["task_revision"] = 1
    return updated


def write_metadata(task_dir: Path, metadata: dict[str, Any]) -> None:
    path = task_dir / "metadata.json"
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
