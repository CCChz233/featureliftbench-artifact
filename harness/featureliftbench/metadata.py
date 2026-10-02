"""Task metadata loading and basic shape validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENTANGLEMENT_LEVELS = {"low", "medium", "high"}
ENTANGLEMENT_TYPES = {
    "framework_coupling",
    "config_environment_coupling",
    "global_state_registry_coupling",
    "resource_coupling",
    "implicit_dependency_coupling",
    "parser_state_coupling",
    "data_model_coupling",
    "third_party_dependency_coupling",
    "legacy_vibe_clutter",
    "internal_packages",
    "reflection_coupling",
    "init_side_effects",
}
ENTANGLEMENT_PRIMARY_TYPES = (
    "framework_coupling",
    "config_environment_coupling",
    "parser_state_coupling",
    "resource_coupling",
    "data_model_coupling",
    "third_party_dependency_coupling",
    "legacy_vibe_clutter",
)


class MetadataError(ValueError):
    """Raised when a task metadata file cannot be read or parsed."""


@dataclass(frozen=True)
class TaskMetadata:
    """Loaded task metadata."""

    path: Path
    data: dict[str, Any]

    @property
    def task_id(self) -> str:
        value = self.data.get("task_id")
        return value if isinstance(value, str) else ""


def load_metadata(path: str | Path) -> TaskMetadata:
    """Load metadata from a task directory or a metadata JSON file."""

    metadata_path = Path(path)
    if metadata_path.is_dir():
        metadata_path = metadata_path / "metadata.json"

    try:
        raw = metadata_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise MetadataError(f"cannot read metadata: {metadata_path}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetadataError(f"invalid metadata JSON: {metadata_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise MetadataError(f"metadata must be a JSON object: {metadata_path}")

    return TaskMetadata(path=metadata_path, data=data)


def validate_metadata_shape(metadata: dict[str, Any]) -> list[str]:
    """Return metadata shape errors.

    This intentionally covers only the MVP contract. The JSON Schema in
    ``schemas/task_metadata.schema.json`` is the longer-term source of truth.
    """

    errors: list[str] = []

    required_top_level = {
        "task_id": str,
        "language": str,
        "source": dict,
        "feature": dict,
        "entanglement": dict,
        "output": dict,
        "environment": dict,
        "tests": dict,
    }
    for key, expected_type in required_top_level.items():
        _require_type(metadata, key, expected_type, errors)

    difficulty = metadata.get("difficulty")
    if difficulty is not None:
        if not isinstance(difficulty, str):
            errors.append(f"field difficulty must be str, got {type(difficulty).__name__}")
        elif difficulty not in {"easy", "medium", "hard"}:
            errors.append("field difficulty must be one of: easy, medium, hard")

    split_role = metadata.get("split_role")
    if split_role is not None:
        if not isinstance(split_role, str):
            errors.append(f"field split_role must be str, got {type(split_role).__name__}")
        elif split_role != "mechanism_challenging":
            errors.append("field split_role must be: mechanism_challenging")

    language = metadata.get("language")
    if language is not None:
        if not isinstance(language, str):
            errors.append(f"field language must be str, got {type(language).__name__}")
        elif language not in {"python", "go"}:
            errors.append("field language must be one of: python, go")
    else:
        language = "python"

    tags = metadata.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            errors.append(f"field tags must be list, got {type(tags).__name__}")
        elif any(not isinstance(item, str) for item in tags):
            errors.append("field tags must contain only strings")

    source = metadata.get("source")
    if isinstance(source, dict):
        for key in ("name", "url", "commit", "license"):
            _require_type(metadata, f"source.{key}", str, errors)

    feature = metadata.get("feature")
    if isinstance(feature, dict):
        for key in ("name", "description"):
            _require_type(metadata, f"feature.{key}", str, errors)
        _require_string_list(metadata, "feature.source_entrypoints", errors)
        _require_string_list(metadata, "feature.included_behaviors", errors)
        _require_string_list(metadata, "feature.excluded_behaviors", errors)

    entanglement = metadata.get("entanglement")
    if isinstance(entanglement, dict):
        _require_type(metadata, "entanglement.level", str, errors)
        level = entanglement.get("level")
        if isinstance(level, str) and level not in ENTANGLEMENT_LEVELS:
            errors.append("field entanglement.level must be one of: low, medium, high")
        _require_type(metadata, "entanglement.description", str, errors)
        _require_string_list(metadata, "entanglement.signals", errors)
        _require_string_list(metadata, "entanglement.types", errors)
        types = entanglement.get("types")
        if isinstance(types, list):
            if not types:
                errors.append("field entanglement.types must contain at least one item")
            unknown = sorted(
                {item for item in types if isinstance(item, str) and item not in ENTANGLEMENT_TYPES}
            )
            if unknown:
                errors.append(
                    "field entanglement.types contains unknown values: " + ", ".join(unknown)
                )
        primary = entanglement.get("primary")
        if primary is not None:
            _require_type(metadata, "entanglement.primary", str, errors)
            if isinstance(primary, str) and primary not in ENTANGLEMENT_PRIMARY_TYPES:
                errors.append(
                    "field entanglement.primary must be one of: "
                    + ", ".join(ENTANGLEMENT_PRIMARY_TYPES)
                )
            if (
                isinstance(primary, str)
                and isinstance(types, list)
                and primary not in types
            ):
                errors.append(
                    f"field entanglement.primary must also appear in entanglement.types: {primary}"
                )

    output = metadata.get("output")
    if isinstance(output, dict):
        if language == "go":
            for key in ("package", "import"):
                _require_type(metadata, f"output.{key}", str, errors)
            if "module" in output or "symbols" in output:
                _require_type(metadata, "output.module", str, errors)
                _require_string_list(metadata, "output.symbols", errors)
            else:
                # Keep the original Go pilot schema valid while accepting the
                # stronger module/symbols contract used by newer tasks.
                for key in ("callable", "signature"):
                    _require_type(metadata, f"output.{key}", str, errors)
        else:
            for key in ("package", "import", "callable", "signature"):
                _require_type(metadata, f"output.{key}", str, errors)

    environment = metadata.get("environment")
    if isinstance(environment, dict):
        if language == "go":
            _require_type(metadata, "environment.go", str, errors)
            _require_type(metadata, "environment.network", bool, errors)
            _require_type(metadata, "environment.timeout_seconds", int, errors)
            cgo = environment.get("cgo_enabled")
            if cgo is not None and not isinstance(cgo, bool):
                errors.append("field environment.cgo_enabled must be bool")
            _require_string_list(metadata, "environment.forbidden_imports", errors)
        else:
            _require_type(metadata, "environment.python", str, errors)
            _require_type(metadata, "environment.network", bool, errors)
            _require_type(metadata, "environment.timeout_seconds", int, errors)
            _require_type(metadata, "environment.dependency_lock", str, errors)
            _require_string_list(metadata, "environment.allowed_dependencies", errors)
            _require_string_list(metadata, "environment.forbidden_dependencies", errors)
            _require_string_list(metadata, "environment.forbidden_imports", errors)

    tests = metadata.get("tests")
    if isinstance(tests, dict):
        for key in ("public", "hidden", "command"):
            _require_type(metadata, f"tests.{key}", str, errors)

    scoring_reference = metadata.get("scoring_reference")
    if scoring_reference is not None:
        if not isinstance(scoring_reference, dict):
            errors.append(
                f"field scoring_reference must be dict, got {type(scoring_reference).__name__}"
            )
            return errors
        for key in (
            "copy_all_bytes",
            "copy_all_loc",
            "oracle_bytes",
            "oracle_loc",
            "oracle_dependency_count",
        ):
            _require_number(metadata, f"scoring_reference.{key}", errors)

    return errors


def _lookup(data: dict[str, Any], dotted_key: str) -> Any:
    current: Any = data
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _require_type(
    data: dict[str, Any],
    dotted_key: str,
    expected_type: type,
    errors: list[str],
) -> None:
    value = _lookup(data, dotted_key)
    if value is None:
        errors.append(f"missing required field: {dotted_key}")
        return
    if not isinstance(value, expected_type):
        errors.append(
            f"field {dotted_key} must be {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )


def _require_number(data: dict[str, Any], dotted_key: str, errors: list[str]) -> None:
    value = _lookup(data, dotted_key)
    if value is None:
        errors.append(f"missing required field: {dotted_key}")
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errors.append(f"field {dotted_key} must be number, got {type(value).__name__}")


def _require_string_list(
    data: dict[str, Any],
    dotted_key: str,
    errors: list[str],
) -> None:
    value = _lookup(data, dotted_key)
    if value is None:
        errors.append(f"missing required field: {dotted_key}")
        return
    if not isinstance(value, list):
        errors.append(f"field {dotted_key} must be list, got {type(value).__name__}")
        return
    bad_items = [item for item in value if not isinstance(item, str)]
    if bad_items:
        errors.append(f"field {dotted_key} must contain only strings")
