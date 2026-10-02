"""Programmatic calibration cases with construction-derived verdicts."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any


CANARY_SCHEMA = "featureliftbench.agentic_evidence.canary_suite.v1"
CANARY_CLASSES = ("explicit", "recoverable", "ambiguous", "underdetermined")

_EXAMPLES = (
    ("Straße", "strasse"),
    ("ẞ", "ss"),
    ("ﬃ", "ffi"),
    ("ＡＢＣ", "abc"),
    ("①", "1"),
    ("ℌELLO", "hello"),
    ("ﬁle", "file"),
    ("Ⅳ", "iv"),
    ("Ⓐ", "a"),
    ("㎏", "kg"),
)


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _public_spec(case_id: str, verdict: str) -> dict[str, Any]:
    behavior = (
        "normalize(value) must apply Unicode NFKC normalization followed by "
        "casefolding."
        if verdict == "explicit"
        else "normalize(value) preserves the repository's canonical text semantics."
    )
    return {
        "schema_version": "featureliftbench.task.v1",
        "task_id": case_id,
        "public_spec": {
            "title": "Canonical text normalization",
            "summary": "Extract the repository's canonical text normalization behavior.",
            "required_api": [
                {"path": "featurelifted.normalize", "kind": "function"}
            ],
            "behaviors": [{"id": "B001", "text": behavior}],
        },
    }


def _task_markdown(verdict: str) -> str:
    detail = (
        "The function must apply Unicode NFKC normalization followed by "
        "casefolding.\n"
        if verdict == "explicit"
        else "Preserve the repository's canonical text semantics.\n"
    )
    return (
        "# Canonical text normalization\n\n"
        "Create `featurelifted.normalize(value)`.\n\n"
        "## Behavior\n\n"
        f"{detail}"
    )


def _repository_files(verdict: str) -> dict[str, str]:
    canonical = (
        "\"\"\"Canonical normalization used by the public API.\"\"\"\n"
        "import unicodedata\n\n"
        "def normalize(value: str) -> str:\n"
        "    return unicodedata.normalize(\"NFKC\", value).casefold()\n"
    )
    if verdict in {"explicit", "recoverable"}:
        return {
            "repo/textcore/normalize.py": canonical,
            "repo/textcore/api.py": (
                "from .normalize import normalize\n\n__all__ = [\"normalize\"]\n"
            ),
            "repo/tests/test_normalize.py": (
                "from textcore import normalize\n\n"
                "def test_canonical_text():\n"
                "    assert normalize(\"Straße\") == \"strasse\"\n"
            ),
        }
    if verdict == "ambiguous":
        return {
            "repo/textcore/legacy.py": (
                "def normalize(value: str) -> str:\n"
                "    return value.lower()\n"
            ),
            "repo/textcore/unicode.py": (
                "\"\"\"Supported Unicode normalization backend.\"\"\"\n"
                "import unicodedata\n\n"
                "def normalize(value: str) -> str:\n"
                "    return unicodedata.normalize(\"NFKC\", value).casefold()\n"
            ),
            "repo/textcore/api.py": (
                "# Backend selection is performed by downstream applications.\n"
                "# Both implementations remain supported.\n"
            ),
        }
    return {
        "repo/textcore/api.py": (
            "def display(value: str) -> str:\n"
            "    return value.strip()\n"
        ),
        "repo/README.md": (
            "This package contains application-specific text helpers.\n"
        ),
    }


def _write_case(case_dir: Path, *, case_id: str, verdict: str, index: int) -> None:
    case_dir.mkdir(parents=True, exist_ok=False)
    metadata = _public_spec(case_id, verdict)
    (case_dir / "metadata.json").write_text(
        _json_text(metadata), encoding="utf-8"
    )
    (case_dir / "TASK.md").write_text(_task_markdown(verdict), encoding="utf-8")
    for relative, content in _repository_files(verdict).items():
        destination = case_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    source, expected = _EXAMPLES[index]
    packet = {
        "schema_version": "featureliftbench.agentic_evidence.canary_packet.v1",
        "task_id": case_id,
        "nodeid": f"private_evaluator/test_normalize.py::test_case_{index + 1:02d}",
        "assertion": f"normalize({source!r}) == {expected!r}",
        "instruction": (
            "Classify whether this evaluator behavior is explicit, recoverable, "
            "ambiguous, or underdetermined from TASK.md, metadata.public_spec, "
            "and repo/. Cite only those public inputs."
        ),
    }
    (case_dir / "audit_packet.json").write_text(
        _json_text(packet), encoding="utf-8"
    )


def generate_canary_suite(
    output_dir: str | Path,
    *,
    per_class: int = 10,
    seed: int = 20260820,
) -> dict[str, Any]:
    """Generate opaque case directories and a private expected-label manifest."""

    if per_class < 1 or per_class > len(_EXAMPLES):
        raise ValueError(f"per_class must be in [1, {len(_EXAMPLES)}]")
    root = Path(output_dir)
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"output directory must be absent or empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    rows = [
        (verdict, index)
        for verdict in CANARY_CLASSES
        for index in range(per_class)
    ]
    random.Random(seed).shuffle(rows)
    cases: list[dict[str, Any]] = []
    for ordinal, (verdict, index) in enumerate(rows, start=1):
        opaque = hashlib.sha256(
            f"{seed}:{ordinal}:{verdict}:{index}".encode("utf-8")
        ).hexdigest()[:12]
        case_id = f"canary_{opaque}"
        _write_case(
            root / "cases" / case_id,
            case_id=case_id,
            verdict=verdict,
            index=index,
        )
        cases.append(
            {
                "case_id": case_id,
                "expected_verdict": verdict,
                "metamorphic_family": f"normalize_{index + 1:02d}",
            }
        )
    manifest = {
        "schema_version": CANARY_SCHEMA,
        "seed": seed,
        "per_class": per_class,
        "case_count": len(cases),
        "classes": list(CANARY_CLASSES),
        "cases": cases,
    }
    (root / "private_manifest.json").write_text(
        _json_text(manifest), encoding="utf-8"
    )
    return manifest


def validate_canary_suite(root: str | Path) -> list[str]:
    base = Path(root)
    manifest_path = base / "private_manifest.json"
    if not manifest_path.is_file():
        return ["missing private_manifest.json"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid private_manifest.json: {exc}"]
    errors: list[str] = []
    if manifest.get("schema_version") != CANARY_SCHEMA:
        errors.append(f"unexpected manifest schema: {manifest.get('schema_version')!r}")
    expected_counts = {label: 0 for label in CANARY_CLASSES}
    seen: set[str] = set()
    for row in manifest.get("cases") or []:
        case_id = str(row.get("case_id") or "")
        verdict = str(row.get("expected_verdict") or "")
        if not case_id or case_id in seen:
            errors.append(f"invalid or duplicate case_id: {case_id!r}")
            continue
        seen.add(case_id)
        if verdict not in expected_counts:
            errors.append(f"invalid expected verdict for {case_id}: {verdict!r}")
            continue
        expected_counts[verdict] += 1
        case_dir = base / "cases" / case_id
        for relative in ("TASK.md", "metadata.json", "audit_packet.json", "repo"):
            if not (case_dir / relative).exists():
                errors.append(f"{case_id}: missing {relative}")
        public_blob = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(case_dir.rglob("*"))
            if path.is_file()
        ).lower()
        if "expected_verdict" in public_blob:
            errors.append(f"{case_id}: expected label leaked into public case files")
    per_class = manifest.get("per_class")
    if isinstance(per_class, int):
        for verdict, count in expected_counts.items():
            if count != per_class:
                errors.append(
                    f"class {verdict} has {count} cases, expected {per_class}"
                )
    if manifest.get("case_count") != len(seen):
        errors.append(
            f"manifest case_count={manifest.get('case_count')} but found {len(seen)}"
        )
    return errors
