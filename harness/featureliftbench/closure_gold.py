"""Load and score auditable dependency-closure gold annotations.

The v1.1 format scores *requirements*, not individual alternative artifacts.
This matters for replaceable dependencies: an upstream symbol, an adapter, and
an approved reimplementation are three ways to satisfy one requirement, not
three recall units.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


GOLD_FILENAME = "closure_gold.json"
ORACLE_MANIFEST_FILENAME = "oracle_manifest.json"
COMPLETE = "complete"
PARTIAL = "partial"
UNRESOLVED = "unresolved"
LEGACY = "legacy_unreviewed"
REQUIREMENT_KINDS = {
    "file",
    "symbol",
    "resource",
    "runtime_state",
    "third_party",
    "adapter",
}
NECESSITIES = {"must", "optional"}


@dataclass(frozen=True)
class ClosureArtifact:
    """One concrete artifact inside a solution bundle."""

    kind: str
    value: str

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.value}"


@dataclass(frozen=True)
class ClosureSolution:
    """One approved, complete way to satisfy a requirement."""

    solution_id: str
    artifacts: tuple[ClosureArtifact, ...]


@dataclass(frozen=True)
class ClosureRequirement:
    """The atomic unit used in closure recall."""

    requirement_id: str
    kind: str
    necessity: str
    satisfied_by: tuple[ClosureSolution, ...]
    evidence_paths: tuple[str, ...] = ()
    behavior_ids: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True)
class ClosureVariant:
    variant_id: str
    requirements: tuple[ClosureRequirement, ...]


@dataclass(frozen=True)
class ClosureGold:
    task_id: str
    source: str
    schema_version: str
    variants: tuple[ClosureVariant, ...]
    completeness: dict[str, str]
    annotation_status: str
    path: Path | None
    errors: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return bool(self.variants)

    def completeness_for(self, kind: str) -> str:
        return self.completeness.get(kind, UNRESOLVED)

    def scoreable(self, kind: str) -> bool:
        return self.completeness_for(kind) == COMPLETE

    def approved_artifact_values(self, kind: str = "file") -> set[str]:
        values: set[str] = set()
        for variant in self.variants:
            for requirement in variant.requirements:
                if requirement.kind != kind:
                    continue
                for solution in requirement.satisfied_by:
                    values.update(artifact.value for artifact in solution.artifacts if artifact.kind == kind)
        return values


@dataclass(frozen=True)
class ClosureScore:
    kind: str
    variant_id: str
    precision: float
    recall: float
    f1: float
    required_requirement_count: int
    satisfied_requirement_count: int
    matched_optional_requirement_count: int
    unmatched_prediction_count: int
    redundant_alternative_count: int
    predicted_artifact_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "variant_id": self.variant_id,
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1": round(self.f1, 6),
            "required_requirement_count": self.required_requirement_count,
            "satisfied_requirement_count": self.satisfied_requirement_count,
            "matched_optional_requirement_count": self.matched_optional_requirement_count,
            "unmatched_prediction_count": self.unmatched_prediction_count,
            "redundant_alternative_count": self.redundant_alternative_count,
            "predicted_artifact_count": self.predicted_artifact_count,
        }


def load_closure_gold(task_dir: str | Path, *, allow_legacy: bool = True) -> ClosureGold:
    """Load v1.1 gold, optionally falling back to an unreviewed legacy manifest.

    Legacy manifests are deliberately marked ``legacy_unreviewed`` and are not
    scoreable.  Consumers may use their file list as an oracle hint, but must
    not report closure P/R/F1 until a reviewer marks file gold complete.
    """

    task_path = Path(task_dir)
    gold_path = task_path / "evaluation" / GOLD_FILENAME
    if gold_path.is_file():
        return _load_v11_gold(task_path, gold_path)
    if allow_legacy:
        return _load_legacy_gold(task_path)
    return ClosureGold(
        task_id=task_path.name,
        source="missing",
        schema_version="",
        variants=(),
        completeness={},
        annotation_status="missing",
        path=None,
        errors=("closure gold is missing",),
    )


def score_closure(
    gold: ClosureGold,
    predicted: Iterable[str | ClosureArtifact],
    *,
    kind: str = "file",
) -> ClosureScore | None:
    """Score predictions against complete gold and the best accepted variant.

    A solution bundle is satisfied only when all of its artifacts are present.
    Multiple satisfied alternatives for one requirement still contribute one
    recall true positive; the extras are exposed as redundancy instead.
    """

    if not gold.scoreable(kind):
        return None
    predicted_keys = {_prediction_key(value, kind=kind) for value in predicted}
    predicted_keys.discard("")
    scores = [
        _score_variant(variant, predicted_keys, kind=kind)
        for variant in gold.variants
    ]
    if not scores:
        return None
    return max(scores, key=lambda item: (item.f1, item.recall, item.precision, item.variant_id))


def normalize_source_path(raw: str, task_dir: str | Path) -> str | None:
    """Normalize manifest/source paths to ``repo/...`` task-relative paths."""

    task_path = Path(task_dir)
    text = raw.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if not text:
        return None
    absolute_task = task_path.resolve().as_posix().rstrip("/") + "/"
    if text.startswith(absolute_task):
        text = text[len(absolute_task) :]
    if text.startswith("repo/"):
        candidate = task_path / text
        return PurePosixPath(text).as_posix() if candidate.exists() else None
    candidate = task_path / "repo" / text
    if candidate.exists():
        return (PurePosixPath("repo") / PurePosixPath(text)).as_posix()
    candidate = task_path / text
    if candidate.exists() and "repo" in candidate.parts:
        return candidate.relative_to(task_path).as_posix()
    return None


def validate_closure_gold(gold: ClosureGold) -> list[str]:
    errors = list(gold.errors)
    seen_variants: set[str] = set()
    for variant in gold.variants:
        if variant.variant_id in seen_variants:
            errors.append(f"duplicate variant_id: {variant.variant_id}")
        seen_variants.add(variant.variant_id)
        seen_requirements: set[str] = set()
        for requirement in variant.requirements:
            if requirement.requirement_id in seen_requirements:
                errors.append(
                    f"{variant.variant_id}: duplicate requirement_id: {requirement.requirement_id}"
                )
            seen_requirements.add(requirement.requirement_id)
            if requirement.kind not in REQUIREMENT_KINDS:
                errors.append(
                    f"{variant.variant_id}/{requirement.requirement_id}: unknown kind {requirement.kind}"
                )
            if requirement.necessity not in NECESSITIES:
                errors.append(
                    f"{variant.variant_id}/{requirement.requirement_id}: "
                    f"unknown necessity {requirement.necessity}"
                )
            if not requirement.satisfied_by:
                errors.append(
                    f"{variant.variant_id}/{requirement.requirement_id}: satisfied_by is empty"
                )
    return errors


def _load_v11_gold(task_dir: Path, path: Path) -> ClosureGold:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ClosureGold(
            task_id=task_dir.name,
            source="closure_gold",
            schema_version="",
            variants=(),
            completeness={},
            annotation_status="invalid",
            path=path,
            errors=(f"invalid closure gold JSON: {exc}",),
        )
    if not isinstance(payload, dict):
        payload = {}
    raw_completeness = payload.get("gold_completeness")
    if isinstance(raw_completeness, str):
        completeness = {kind: raw_completeness for kind in REQUIREMENT_KINDS}
    elif isinstance(raw_completeness, dict):
        completeness = {
            str(kind): str(value)
            for kind, value in raw_completeness.items()
            if str(value) in {COMPLETE, PARTIAL, UNRESOLVED}
        }
    else:
        completeness = {}
    variants = tuple(
        _parse_variant(raw, task_dir)
        for raw in payload.get("closure_variants") or []
        if isinstance(raw, dict)
    )
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    gold = ClosureGold(
        task_id=str(payload.get("task_id") or task_dir.name),
        source="closure_gold",
        schema_version=str(payload.get("schema_version") or ""),
        variants=variants,
        completeness=completeness,
        annotation_status=str(review.get("status") or "unreviewed"),
        path=path,
    )
    return ClosureGold(**{**gold.__dict__, "errors": tuple(validate_closure_gold(gold))})


def _parse_variant(raw: dict[str, Any], task_dir: Path) -> ClosureVariant:
    requirements = tuple(
        _parse_requirement(value, task_dir)
        for value in raw.get("requirements") or []
        if isinstance(value, dict)
    )
    return ClosureVariant(
        variant_id=str(raw.get("variant_id") or "default"),
        requirements=requirements,
    )


def _parse_requirement(raw: dict[str, Any], task_dir: Path) -> ClosureRequirement:
    kind = str(raw.get("kind") or "file")
    solutions: list[ClosureSolution] = []
    for index, value in enumerate(raw.get("satisfied_by") or []):
        if isinstance(value, str):
            artifacts = (ClosureArtifact(kind=kind, value=_normalize_artifact(kind, value, task_dir)),)
            solutions.append(ClosureSolution(solution_id=value, artifacts=artifacts))
            continue
        if not isinstance(value, dict):
            continue
        raw_artifacts = value.get("artifacts")
        if not isinstance(raw_artifacts, list):
            raw_artifacts = [value]
        artifacts = tuple(
            artifact
            for item in raw_artifacts
            if isinstance(item, (str, dict))
            if (artifact := _parse_artifact(item, default_kind=kind, task_dir=task_dir)) is not None
        )
        solutions.append(
            ClosureSolution(
                solution_id=str(value.get("solution_id") or f"solution_{index + 1}"),
                artifacts=artifacts,
            )
        )
    return ClosureRequirement(
        requirement_id=str(raw.get("requirement_id") or ""),
        kind=kind,
        necessity=str(raw.get("necessity") or "must"),
        satisfied_by=tuple(solutions),
        evidence_paths=tuple(str(value) for value in raw.get("evidence_paths") or []),
        behavior_ids=tuple(str(value) for value in raw.get("behavior_ids") or []),
        rationale=str(raw.get("rationale") or ""),
    )


def _parse_artifact(
    raw: str | dict[str, Any], *, default_kind: str, task_dir: Path
) -> ClosureArtifact | None:
    if isinstance(raw, str):
        return ClosureArtifact(default_kind, _normalize_artifact(default_kind, raw, task_dir))
    kind = str(raw.get("kind") or default_kind)
    if kind == "file":
        value = raw.get("source_path") or raw.get("path") or raw.get("value")
    elif kind == "symbol":
        module = str(raw.get("module") or "")
        symbol = str(raw.get("symbol") or raw.get("value") or "")
        value = f"{module}:{symbol}" if module else symbol
    elif kind == "runtime_state":
        value = raw.get("behavior_probe") or raw.get("value")
    else:
        value = raw.get("value") or raw.get("source_path") or raw.get("module")
    if not isinstance(value, str) or not value:
        return None
    return ClosureArtifact(kind, _normalize_artifact(kind, value, task_dir))


def _normalize_artifact(kind: str, value: str, task_dir: Path) -> str:
    if kind != "file":
        return value.strip()
    return normalize_source_path(value, task_dir) or value.strip().replace("\\", "/")


def _load_legacy_gold(task_dir: Path) -> ClosureGold:
    path = task_dir / "evaluation" / ORACLE_MANIFEST_FILENAME
    if not path.is_file():
        return ClosureGold(
            task_id=task_dir.name,
            source="missing",
            schema_version="",
            variants=(),
            completeness={},
            annotation_status="missing",
            path=None,
            errors=("closure gold and oracle manifest are missing",),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ClosureGold(
            task_id=task_dir.name,
            source="oracle_manifest",
            schema_version="legacy",
            variants=(),
            completeness={"file": UNRESOLVED},
            annotation_status="invalid",
            path=path,
            errors=(f"invalid oracle manifest JSON: {exc}",),
        )
    values = payload.get("required_source_files")
    field = "required_source_files"
    if not isinstance(values, list):
        values = payload.get("source_files")
        field = "source_files"
    requirements: list[ClosureRequirement] = []
    errors: list[str] = []
    for index, raw in enumerate(values or []):
        if not isinstance(raw, str):
            continue
        normalized = normalize_source_path(raw, task_dir)
        if normalized is None:
            errors.append(f"legacy manifest path does not exist: {raw}")
            continue
        artifact = ClosureArtifact("file", normalized)
        requirements.append(
            ClosureRequirement(
                requirement_id=f"legacy_file_{index + 1:03d}",
                kind="file",
                necessity="must",
                satisfied_by=(ClosureSolution("original_file", (artifact,)),),
                evidence_paths=(f"evaluation/{ORACLE_MANIFEST_FILENAME}#{field}[{index}]",),
                rationale="Imported from an unreviewed legacy oracle manifest.",
            )
        )
    completeness = {"file": LEGACY if requirements else UNRESOLVED}
    variants = (
        (ClosureVariant("legacy_manifest", tuple(requirements)),)
        if requirements
        else ()
    )
    return ClosureGold(
        task_id=task_dir.name,
        source="oracle_manifest",
        schema_version="legacy",
        variants=variants,
        completeness=completeness,
        annotation_status="auto_assigned",
        path=path,
        errors=tuple(errors),
    )


def _prediction_key(value: str | ClosureArtifact, *, kind: str) -> str:
    if isinstance(value, ClosureArtifact):
        return value.key
    text = value.strip().replace("\\", "/")
    if not text:
        return ""
    if text.startswith(f"{kind}:"):
        return text
    return f"{kind}:{text}"


def _score_variant(
    variant: ClosureVariant, predicted_keys: set[str], *, kind: str
) -> ClosureScore:
    requirements = [item for item in variant.requirements if item.kind == kind]
    required = [item for item in requirements if item.necessity != "optional"]
    optional = [item for item in requirements if item.necessity == "optional"]
    accepted_keys: set[str] = set()
    satisfied_required = 0
    matched_optional = 0
    redundant = 0
    for requirement in requirements:
        satisfied_solutions = 0
        for solution in requirement.satisfied_by:
            solution_keys = {artifact.key for artifact in solution.artifacts}
            accepted_keys.update(solution_keys)
            if solution_keys and solution_keys <= predicted_keys:
                satisfied_solutions += 1
        if satisfied_solutions:
            if requirement.necessity == "optional":
                matched_optional += 1
            else:
                satisfied_required += 1
            redundant += max(0, satisfied_solutions - 1)
    unmatched = len(predicted_keys - accepted_keys)
    matched_groups = satisfied_required + matched_optional
    precision_denominator = matched_groups + unmatched
    precision = matched_groups / precision_denominator if precision_denominator else 1.0
    recall = satisfied_required / len(required) if required else 1.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return ClosureScore(
        kind=kind,
        variant_id=variant.variant_id,
        precision=precision,
        recall=recall,
        f1=f1,
        required_requirement_count=len(required),
        satisfied_requirement_count=satisfied_required,
        matched_optional_requirement_count=matched_optional,
        unmatched_prediction_count=unmatched,
        redundant_alternative_count=redundant,
        predicted_artifact_count=len(predicted_keys),
    )
