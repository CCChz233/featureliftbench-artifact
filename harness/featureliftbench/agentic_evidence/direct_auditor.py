"""Direct structured audit for small calibration cases without a tool Agent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from .citation_validator import build_citation
from .schema import AUDIT_RECORD_SCHEMA


def render_case_prompt(case_dir: str | Path, *, agent_id: str) -> str:
    root = Path(case_dir)
    chunks = [
        "You are an evidence auditor. Classify the evaluator assertion from only "
        "the public task contract and repository evidence provided below.\n",
        "Verdicts: explicit, recoverable, ambiguous, underdetermined, abstain.\n",
        "Use ambiguous when public repository evidence supports two or more "
        "incompatible target semantics and the public contract does not select "
        "one; cite both sides. Use underdetermined when the public inputs provide "
        "no sufficient implementation evidence to determine the behavior.\n",
        "Recoverable requires one unique target behavior, not merely one matching "
        "implementation. Search the supplied files for competing semantics.\n",
        "Return one JSON object. Citation proposals contain path, kind, start_line, "
        "end_line, and claim; kind must be task, public_spec, or repository. The "
        "caller will compute hashes. Ambiguous requires "
        "both evidence and counterevidence. Do not include markdown fences.\n",
        "Required keys: task_id, nodeid, verdict, confidence, "
        "public_obligation_ids, evidence, counterevidence, abstain_reason.\n",
        f"The fixed agent_id is {agent_id!r}.\n",
    ]
    selected = [root / "TASK.md", root / "metadata.json", root / "audit_packet.json"]
    selected.extend(
        path for path in sorted((root / "repo").rglob("*")) if path.is_file()
    )
    for path in selected:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="strict")
        numbered = "\n".join(
            f"{index:04d}: {line}"
            for index, line in enumerate(text.splitlines(), start=1)
        )
        chunks.append(f"\n===== {relative} =====\n{numbered}\n")
    return "".join(chunks)


def parse_json_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1)
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Agent response must be a JSON object")
    return payload


def _finalize_citations(
    task_dir: Path,
    values: Any,
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        raise ValueError("citation proposals must be a list")
    result: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise ValueError(f"citation proposal {index} must be an object")
        try:
            path = str(value["path"])
            proposed_kind = str(value.get("kind") or "")
            if path == "TASK.md":
                kind = "task"
            elif path == "metadata.json":
                kind = "public_spec"
            elif path.startswith("repo/"):
                kind = "repository"
            else:
                kind = proposed_kind
            result.append(
                build_citation(
                    task_dir,
                    path=path,
                    kind=kind,
                    start_line=int(value["start_line"]),
                    end_line=int(value["end_line"]),
                    claim=str(value["claim"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid citation proposal {index}: {exc}") from exc
    return result


def coerce_confidence(value: Any, *, default: float = 0.5) -> float:
    """Coerce Agent confidence to a float in [0, 1]."""

    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        stripped = value.strip().rstrip("%")
        try:
            parsed = float(stripped)
        except ValueError:
            return default
        if parsed > 1.0 and parsed <= 100.0:
            parsed = parsed / 100.0
        return max(0.0, min(1.0, parsed))
    return default


def finalize_proposed_record(
    proposal: Mapping[str, Any],
    *,
    task_dir: str | Path,
    agent_id: str,
) -> dict[str, Any]:
    root = Path(task_dir)
    obligations = proposal.get("public_obligation_ids")
    if not isinstance(obligations, list):
        obligations = []
    return {
        "schema_version": AUDIT_RECORD_SCHEMA,
        "task_id": str(proposal.get("task_id") or ""),
        "nodeid": str(proposal.get("nodeid") or ""),
        "agent_id": agent_id,
        "verdict": str(proposal.get("verdict") or "").lower(),
        "confidence": coerce_confidence(proposal.get("confidence")),
        "public_obligation_ids": [str(value) for value in obligations],
        "evidence": _finalize_citations(root, proposal.get("evidence") or []),
        "counterevidence": _finalize_citations(
            root, proposal.get("counterevidence") or []
        ),
        "abstain_reason": str(proposal.get("abstain_reason") or ""),
    }
