"""Deterministic 30-task pilot sample from Pro/Flash artifact failures.

Does not invent task IDs. If the annotation CSV or suites cannot fill
15 public + 15 hidden unique tasks, sampling fails.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any
from typing import Iterable
from typing import Mapping

SEED = "obligation-guided-pilot30-v1"
N_PUBLIC = 15
N_HIDDEN = 15
PREFERRED_CAUSES = frozenset(
    {"behavior_drift", "contract_api_completion", "dependency_closure"}
)
CAC_CAUSES = frozenset({"contract_api_completion"})
EXCLUDED_CAUSES = frozenset(
    {
        "agent_process_non_delivery",
        "task_or_evaluator_defect",
        "test_gaming_narrow",
    }
)
PUBLIC_STAGES = frozenset({"public", "public_failure", "public_tests"})
HIDDEN_STAGES = frozenset({"hidden", "hidden_failure", "hidden_tests"})
FLASH_MODELS = ("flash", "deepseek-v4-flash", "deepseek/deepseek-v4-flash")
PRO_MODELS = ("pro", "deepseek-v4-pro", "deepseek/deepseek-v4-pro")


def normalize_stage(value: str) -> str:
    text = str(value or "").strip().lower()
    if text in PUBLIC_STAGES:
        return "public"
    if text in HIDDEN_STAGES:
        return "hidden"
    if text in {"isolation", "isolation_failure"}:
        return "isolation"
    if text in {"build", "build_failure"}:
        return "build"
    if text in {"missing_submission", "no_submission"}:
        return "missing_submission"
    return text


def normalize_model(value: str) -> str:
    text = str(value or "").strip().lower()
    if any(token in text for token in FLASH_MODELS) or text.endswith("flash"):
        return "flash"
    if any(token in text for token in PRO_MODELS) or text.endswith("pro"):
        return "pro"
    return text or "unknown"


def model_rank(model: str) -> int:
    """Prefer Flash as the paired Main baseline when both models failed."""

    normalized = normalize_model(model)
    if normalized == "flash":
        return 0
    if normalized == "pro":
        return 1
    return 2


def first_failure_from_eval(result: Mapping[str, Any] | None) -> str:
    if not result:
        return "missing_submission"
    scores = result.get("scores") if isinstance(result.get("scores"), dict) else {}
    gate = scores.get("functional_gate")
    try:
        if float(gate or 0.0) >= 1.0:
            return "pass"
    except (TypeError, ValueError):
        pass
    if result.get("build_pass") is False:
        return "build"
    public = result.get("public_tests")
    if isinstance(public, dict) and public.get("passed") is False:
        return "public"
    if result.get("public_tests_pass") is False:
        return "public"
    hidden = result.get("hidden_tests")
    if isinstance(hidden, dict) and hidden.get("passed") is False:
        return "hidden"
    if result.get("hidden_tests_pass") is False:
        return "hidden"
    isolation = result.get("isolation")
    if isinstance(isolation, dict) and isolation.get("passed") is False:
        return "isolation"
    if result.get("isolation_pass") is False:
        return "isolation"
    return "other"


def load_annotation_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [{str(k): str(v or "") for k, v in row.items()} for row in csv.DictReader(handle)]


def python150_task_ids(tasks_root: Path) -> set[str]:
    return {
        path.name
        for path in tasks_root.iterdir()
        if path.is_dir() and (path / "metadata.json").is_file()
    }


def _has_submission(suite_dir: Path, task_id: str) -> bool:
    root = suite_dir / task_id / "submission"
    if (root / "featurelifted").is_dir():
        return True
    if not root.is_dir():
        return False
    return any(root.iterdir())


def _eval_result(suite_dir: Path, task_id: str) -> dict[str, Any]:
    path = suite_dir / task_id / "eval" / "result.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def artifact_failure_rows_from_suite(
    *,
    suite_dir: Path,
    model: str,
    allowed_task_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    """Mechanical artifact failures: has submission, Functional fail, public/hidden first."""

    suite_path = suite_dir / "suite.json"
    if not suite_path.is_file():
        return []
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for run in suite.get("runs") or []:
        if not isinstance(run, dict):
            continue
        task_id = str(run.get("task_id") or "").strip()
        if not task_id:
            continue
        if allowed_task_ids is not None and task_id not in allowed_task_ids:
            continue
        result = _eval_result(suite_dir, task_id)
        stage = first_failure_from_eval(result)
        if stage not in {"public", "hidden"}:
            continue
        if not _has_submission(suite_dir, task_id):
            continue
        rows.append(
            {
                "task_id": task_id,
                "model": model,
                "first_failure_stage": stage,
                "root_cause_primary": "",
                "evidence_eligibility": "valid_agent_evidence",
            }
        )
    return rows


def attach_stages_from_suites(
    rows: list[dict[str, str]],
    *,
    flash_suite: Path | None = None,
    pro_suite: Path | None = None,
) -> list[dict[str, str]]:
    """Fill first_failure_stage from eval/result.json when the CSV omitted it."""

    suites = {
        "flash": flash_suite,
        "pro": pro_suite,
    }
    filled: list[dict[str, str]] = []
    for row in rows:
        current = dict(row)
        stage = normalize_stage(current.get("first_failure_stage") or "")
        if stage in {"public", "hidden"}:
            current["first_failure_stage"] = stage
            filled.append(current)
            continue
        model = normalize_model(current.get("model") or "")
        suite_dir = suites.get(model)
        if suite_dir is None or not suite_dir.is_dir():
            filled.append(current)
            continue
        result = _eval_result(suite_dir, current["task_id"])
        current["first_failure_stage"] = first_failure_from_eval(result)
        filled.append(current)
    return filled


def eligible_rows(rows: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    eligible: list[dict[str, str]] = []
    for raw in rows:
        task_id = str(raw.get("task_id") or "").strip()
        if not task_id:
            continue
        cause = str(raw.get("root_cause_primary") or "").strip()
        override = str(raw.get("validity_override") or "").strip()
        if cause in EXCLUDED_CAUSES or override == "benchmark_invalid_candidate":
            continue
        eligibility = str(raw.get("evidence_eligibility") or "").strip()
        if eligibility and eligibility != "valid_agent_evidence":
            continue
        stage = normalize_stage(str(raw.get("first_failure_stage") or ""))
        if stage not in {"public", "hidden"}:
            continue
        eligible.append(
            {
                "task_id": task_id,
                "model": str(raw.get("model") or "").strip(),
                "first_failure_stage": stage,
                "root_cause_primary": cause,
                "evidence_eligibility": str(raw.get("evidence_eligibility") or "").strip(),
            }
        )
    return eligible


def dedupe_task_ids(rows: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    """Keep one row per task_id, preferring Flash over Pro."""

    chosen: dict[str, dict[str, str]] = {}
    for row in rows:
        task_id = str(row["task_id"])
        current = chosen.get(task_id)
        candidate = dict(row)
        if current is None or model_rank(candidate["model"]) < model_rank(current["model"]):
            chosen[task_id] = candidate
    return [chosen[key] for key in sorted(chosen)]


def _pick(pool: list[dict[str, str]], n: int, rng: random.Random) -> list[dict[str, str]]:
    preferred = [
        row
        for row in pool
        if not row["root_cause_primary"] or row["root_cause_primary"] in PREFERRED_CAUSES
    ]
    use = preferred if len(preferred) >= n else list(pool)
    if len(use) < n:
        raise ValueError(f"need {n} rows, have {len(use)}")
    cac = [row for row in use if row["root_cause_primary"] in CAC_CAUSES]
    rest = [row for row in use if row["root_cause_primary"] not in CAC_CAUSES]
    rng.shuffle(cac)
    rng.shuffle(rest)
    selected = cac[:n]
    if len(selected) < n:
        selected.extend(rest[: n - len(selected)])
    selected.sort(key=lambda row: row["task_id"])
    return selected


def filter_model(rows: Iterable[Mapping[str, str]], model: str | None) -> list[dict[str, str]]:
    if not model:
        return [dict(row) for row in rows]
    wanted = normalize_model(model)
    return [dict(row) for row in rows if normalize_model(str(row.get("model") or "")) == wanted]


def sample_pilot30(
    rows: Iterable[Mapping[str, str]],
    *,
    seed: str = SEED,
    n_public: int = N_PUBLIC,
    n_hidden: int = N_HIDDEN,
    model: str | None = "flash",
) -> dict[str, Any]:
    eligible = eligible_rows(rows)
    scoped = filter_model(eligible, model)
    unique = dedupe_task_ids(scoped)
    public = [row for row in unique if row["first_failure_stage"] == "public"]
    hidden = [row for row in unique if row["first_failure_stage"] == "hidden"]
    rng = random.Random(seed)
    selected_public = _pick(public, n_public, rng)
    selected_hidden = _pick(hidden, n_hidden, rng)
    selected = selected_public + selected_hidden
    selected.sort(key=lambda row: (row["first_failure_stage"], row["task_id"]))
    cause_counts: dict[str, int] = {}
    for row in selected:
        cause = row["root_cause_primary"] or "unlabeled"
        cause_counts[cause] = cause_counts.get(cause, 0) + 1
    return {
        "schema_version": "featureliftbench.obligation_guided_pilot30.v1",
        "seed": seed,
        "n_public": n_public,
        "n_hidden": n_hidden,
        "pool_eligible": len(eligible),
        "pool_model": model or "all",
        "pool_scoped": len(scoped),
        "pool_unique_tasks": len(unique),
        "pool_public": len(public),
        "pool_hidden": len(hidden),
        "cause_counts": cause_counts,
        "task_ids": [row["task_id"] for row in selected],
        "rows": selected,
        "stop_rule": {
            "kill_if_functional_rescue_le_3": True,
            "expand_if_functional_rescue_ge_8_and_drift_rescues": True,
        },
    }


def write_task_list(path: Path, task_ids: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Obligation-Guided pilot-30. Generated; do not hand-edit."]
    lines.extend(str(task_id) for task_id in task_ids)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
