"""Repository path constants for FeatureLiftBench."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = REPO_ROOT / "benchmark"
TASKS_DIR = BENCHMARK_ROOT / "tasks"
GO_TASKS_DIR = BENCHMARK_ROOT / "go" / "tasks"
GO_STAGING_DIR = BENCHMARK_ROOT / "go" / "staging"
GO_SANITY_TASKS_DIR = BENCHMARK_ROOT / "go" / "sanity"
SANITY_TASKS_DIR = BENCHMARK_ROOT / "sanity"
SUBMISSIONS_DIR = BENCHMARK_ROOT / "submissions"
SOURCES_DIR = BENCHMARK_ROOT / "sources"
VENDOR_WHEELS_DIR = BENCHMARK_ROOT / "vendor-wheels"
EXPERIMENTS_DIR = REPO_ROOT / "experiments"
EXPERIMENTS_SMOKE_DIR = EXPERIMENTS_DIR / "smoke"
EXPERIMENTS_PYTHON_DIR = EXPERIMENTS_DIR / "python"
EXPERIMENTS_PYTHON_OPENHANDS_DIR = EXPERIMENTS_PYTHON_DIR / "openhands"
EXPERIMENTS_GO_DIR = EXPERIMENTS_DIR / "GO"
EXPERIMENTS_GO_OPENHANDS_DIR = EXPERIMENTS_GO_DIR / "openhands"
EVIDENCE_DIR = REPO_ROOT / "evidence"
EVIDENCE_PYTHON_BATCH1_DIR = EVIDENCE_DIR / "python" / "batch1"
EVIDENCE_GO_PILOT_DIR = EVIDENCE_DIR / "go" / "go-pilot"
ARCHIVE_DIR = REPO_ROOT / "archive"
HARNESS_ROOT = REPO_ROOT / "harness"
CONFIG_DIR = HARNESS_ROOT / "config"
SCRIPTS_DIR = HARNESS_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"
AGENT_ROOT = REPO_ROOT / "agent"
METHOD_ROOT = REPO_ROOT / "method"
AGENT_REGISTRY = AGENT_ROOT / "registry.toml"
METHOD_REGISTRY = METHOD_ROOT / "registry.toml"
BENCHMARK_SUITES = BENCHMARK_ROOT / "suites.toml"
DEFAULT_AGENT_CONFIG = CONFIG_DIR / "agents.toml"
DEFAULT_AGENT_CONFIG_EXAMPLE = CONFIG_DIR / "agents.example.toml"
DEFAULT_LOCAL_CONFIG = REPO_ROOT / "flb.local.toml"
DEFAULT_LOCAL_CONFIG_EXAMPLE = REPO_ROOT / "flb.local.toml.example"


def model_experiment_slug(model: str) -> str:
    """Filesystem-safe folder name for a model under openhands/<slug>/."""

    raw = model.strip()
    if "/" in raw:
        raw = raw.split("/")[-1]
    if raw.lower().startswith("openai/"):
        raw = raw.split("/", 1)[-1]
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-").lower()
    return slug or "unknown-model"


def openhands_model_dir(*, track: str, model: str) -> Path:
    """Return experiments/{python|GO}/openhands/<model_slug>/."""

    normalized = track.strip().lower()
    if normalized == "go":
        base = EXPERIMENTS_GO_OPENHANDS_DIR
    else:
        base = EXPERIMENTS_PYTHON_OPENHANDS_DIR
    return base / model_experiment_slug(model)


def resolve_openhands_run_dir(
    *,
    track: str,
    model: str,
    suite_name: str,
    run_name: str,
) -> Path:
    """Resolve output directory for an OpenHands experiment run."""

    if suite_name in {"smoke", "pilot5", "sanity", "custom"} or suite_name.startswith("preflight"):
        return EXPERIMENTS_SMOKE_DIR / run_name
    return openhands_model_dir(track=track, model=model) / run_name


def resolve_task_input(path: str | Path) -> Path:
    """Resolve benchmark shorthand paths to the task dataset root."""

    resolved = Path(path).resolve()
    if resolved in {BENCHMARK_ROOT, TASKS_DIR}:
        return TASKS_DIR
    if resolved.name == "go" and (BENCHMARK_ROOT / "go" / "tasks").is_dir():
        return BENCHMARK_ROOT / "go" / "tasks"
    legacy_tasks = REPO_ROOT / "tasks"
    if resolved == legacy_tasks and TASKS_DIR.is_dir():
        return TASKS_DIR
    return resolved


def task_language(task_dir: str | Path) -> str:
    """Return task language from metadata, defaulting to python."""

    from .metadata import load_metadata

    try:
        return str(load_metadata(task_dir).data.get("language", "python"))
    except Exception:
        return "python"
