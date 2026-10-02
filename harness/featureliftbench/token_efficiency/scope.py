"""Official Python-150 × 6 configuration scope for this analysis."""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .constants import CONFIG_ORDER
from .util import csv_bool, read_json


@dataclass(frozen=True)
class OfficialRun:
    run_id: str
    configuration: str
    display_name: str
    short_name: str
    task_id: str
    suite_id: str
    source_run_dir: str
    mapped_run_dir: str
    final_pass: bool
    lift_type: str
    official_tokens: int | None
    original_steps: int | None
    usage_source: str
    usage_unverified: bool
    eval_docker_image: str
    freeze_id: str
    build_pass: bool | None
    public_pass: bool | None
    hidden_pass: bool | None
    isolation_pass: bool | None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_paper_inputs(root: Path | None = None):
    base = root or repo_root()
    path = base / "docs" / "paper" / "paper_inputs.py"
    spec = importlib.util.spec_from_file_location("flb_paper_inputs_token_efficiency", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load paper_inputs from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_official_runs(root: Path | None = None) -> list[OfficialRun]:
    base = (root or repo_root()).resolve()
    paper = load_paper_inputs(base)
    task_ids = paper.paper_task_ids()
    rows = paper.read_csv(paper.RESULTS)
    models = {item["id"]: item for item in paper.MANIFEST["models"]}
    cells = {(row["model"], row["task_id"]): row for row in rows}
    if set(cells) != {(model, task) for model in paper.MODELS for task in task_ids}:
        raise ValueError("main_results is not the official 150×6 grid")
    runs: list[OfficialRun] = []
    for model in CONFIG_ORDER:
        record = models[model]
        suite_dir = (base / record["run_directory"]).resolve()
        suite_id = suite_dir.name
        for task_id in sorted(task_ids):
            row = cells[model, task_id]
            mapped = suite_dir / task_id
            tokens = _optional_int(row.get("process_total_tokens"))
            steps = _optional_int(row.get("process_assistant_steps"))
            runs.append(
                OfficialRun(
                    run_id=f"{model}/{task_id}",
                    configuration=model,
                    display_name=record["display"],
                    short_name=record["short"],
                    task_id=task_id,
                    suite_id=suite_id,
                    source_run_dir=record["run_directory"] + "/" + task_id,
                    mapped_run_dir=str(mapped),
                    final_pass=paper.boolean(row["functional_pass"]),
                    lift_type=row["lift_type"],
                    official_tokens=tokens if tokens else None,
                    original_steps=steps,
                    usage_source=row.get("process_usage_source") or "",
                    usage_unverified=paper.boolean(row["process_usage_unverified"])
                    if row.get("process_usage_unverified") not in {"", None}
                    else False,
                    eval_docker_image=row.get("eval_docker_image") or "",
                    freeze_id=row.get("freeze_id") or "",
                    build_pass=_optional_bool(row.get("build_pass")),
                    public_pass=_optional_bool(row.get("public_pass")),
                    hidden_pass=_optional_bool(row.get("hidden_pass")),
                    isolation_pass=_optional_bool(row.get("isolation_pass")),
                )
            )
    _assert_official_counts(runs, paper)
    return runs


def _assert_official_counts(runs: list[OfficialRun], paper: Any) -> None:
    if len(runs) != 900:
        raise ValueError(f"expected 900 official runs, got {len(runs)}")
    by_model: dict[str, int] = {}
    for run in runs:
        by_model[run.configuration] = by_model.get(run.configuration, 0) + int(run.final_pass)
    for model in CONFIG_ORDER:
        expected = paper.MODEL_RECORDS[model]["main_passes"]
        if by_model[model] != expected:
            raise ValueError(
                f"{model}: official pass count {by_model[model]} != {expected}"
            )


def official_pass_counts(runs: list[OfficialRun]) -> dict[str, int]:
    counts = {model: 0 for model in CONFIG_ORDER}
    for run in runs:
        counts[run.configuration] += int(run.final_pass)
    return counts


def run_as_dict(run: OfficialRun) -> dict[str, Any]:
    return asdict(run)


def _optional_int(value: str | None) -> int | None:
    if value in {None, "", "None"}:
        return None
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number else number


def _optional_bool(value: str | None) -> bool | None:
    if value in {None, ""}:
        return None
    return csv_bool(value)
