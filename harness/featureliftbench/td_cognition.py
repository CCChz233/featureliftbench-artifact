"""TD-Cognition two-phase protocol: cognition scaffold, then implementation.

Phase 1 — Agent produces COGNITION.md + executable probes/ (no submission required).
Phase 2 — Same workspace keeps those artifacts; prompt injects them; Agent implements submission/.

See docs/archive/methods/METHOD_TEST_DRIVEN_COGNITION.md and docs/EVALUATION.md.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Literal


COGNITION_FILE = "COGNITION.md"
PROBES_DIR = "probes"
PHASE_AUDIT_FILE = "td_cognition_phase.json"
TD_PHASE_ENV = "FEATURELIFTBENCH_TD_COGNITION_PHASE"

# Canonical headings (exact substring still preferred in templates).
REQUIRED_COGNITION_HEADINGS = (
    "## Critical Use Cases",
    "## Required Surface",
    "## Support Set Hypothesis",
    "## Exclusions",
    "## Probes",
)

# Soft aliases accepted by the Phase-1 gate (heading text after ##).
_HEADING_ALIASES: dict[str, tuple[str, ...]] = {
    "## Critical Use Cases": (
        "critical use cases",
        "critical use-cases",
        "use cases",
        "critical usecases",
    ),
    "## Required Surface": (
        "required surface",
        "required api surface",
        "api surface",
    ),
    "## Support Set Hypothesis": (
        "support set hypothesis",
        "support set",
        "support-set hypothesis",
    ),
    "## Exclusions": (
        "exclusions",
        "out of scope",
    ),
    "## Probes": (
        "probes",
        "probe plan",
        "probe files",
    ),
}

MIN_USE_CASES = 3
DEFAULT_PROBE_PYTEST_TIMEOUT_SECONDS = 300

PytestBackend = Literal["local", "docker"]


@dataclass(frozen=True)
class CognitionGateResult:
    ok: bool
    errors: tuple[str, ...]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "details": self.details,
        }


def install_td_cognition_workspace(workspace_dir: str | Path) -> dict[str, Any]:
    """Seed cognition templates; keep a normal writable submission/ directory."""

    workspace = Path(workspace_dir).resolve()
    submission = workspace / "submission"
    if submission.is_file() or submission.is_symlink():
        submission.unlink()
    submission.mkdir(exist_ok=True)

    cognition = workspace / COGNITION_FILE
    if not cognition.exists():
        cognition.write_text(cognition_template(), encoding="utf-8")

    probes = workspace / PROBES_DIR
    probes.mkdir(exist_ok=True)
    (probes / "__init__.py").write_text("", encoding="utf-8")
    readme = probes / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Cognition probes\n\n"
            "Write pytest modules here that exercise contract understanding against "
            "`repo/` or standalone assertions.\n"
            "Do **not** import `submission`, `submission.featurelifted`, or any "
            "implementation package in phase-1 probes — they must pass without "
            "`submission/`.\n",
            encoding="utf-8",
        )

    return {
        "td_cognition": True,
        "protocol": "two_phase",
        "submission_locked": False,
        "cognition_file": COGNITION_FILE,
        "probes_dir": PROBES_DIR,
    }


def cognition_template() -> str:
    return (
        "# Cognition Scaffold (TD-Cognition)\n\n"
        "Complete every section in the cognition phase. Do not implement "
        "`submission/featurelifted/` yet.\n\n"
        "## Critical Use Cases\n\n"
        "List at least 3 concrete use cases. Use numbered items "
        "`1.` / `2.` / `3.` (precondition / action / observable result). "
        "Replace the placeholders below — do not leave `...`.\n\n"
        "1. (precondition) … (action) … (observable result) …\n"
        "2. (precondition) … (action) … (observable result) …\n"
        "3. (precondition) … (action) … (observable result) …\n\n"
        "## Required Surface\n\n"
        "- Exports / public API:\n"
        "- Exceptions / error modes:\n"
        "- Resources / config / data files:\n\n"
        "## Support Set Hypothesis\n\n"
        "- Modules/files likely needed from `repo/`:\n\n"
        "## Exclusions\n\n"
        "- Subsystems that must NOT be copied into the package:\n\n"
        "## Probes\n\n"
        "- Probe files under `probes/` and what each asserts:\n"
    )


def phase1_task_appendix() -> str:
    return (
        "### TD-Cognition Phase 1 — Cognition only\n\n"
        "This run is **phase 1 of 2**. Your only job is to build understanding "
        "scaffolding. Here \"tests\" means **your own cognitive probes**, not "
        "benchmark evaluator tests.\n\n"
        "Required outputs before you finish:\n\n"
        "1. Complete `COGNITION.md` (all required headings). Under "
        "`## Critical Use Cases`, write **≥3 numbered** cases as "
        "`1.` / `2.` / `3.` with concrete precondition / action / result "
        "(bullet lists or `### UC1` headings are also accepted by the gate).\n"
        "2. Write executable pytest modules under `probes/` that validate "
        "understanding against `repo/` or standalone contract checks. "
        "**Do not** `import submission`, `submission.featurelifted`, or any "
        "package under `submission/`.\n"
        "3. Run `python -m pytest probes/ -q` and make the probes pass "
        "(green) before finishing phase 1.\n\n"
        "**Do not** implement `submission/featurelifted/` in this phase. "
        "An empty `submission/` directory may exist; leave it empty.\n"
    )


def phase2_task_appendix(*, cognition_text: str, probe_files: list[str]) -> str:
    probe_list = "\n".join(f"- `{name}`" for name in probe_files) or "- (no probe files found)"
    body = cognition_text.strip() if cognition_text.strip() else "_(COGNITION.md missing or empty)_"
    return (
        "### TD-Cognition Phase 2 — Implement from cognition scaffold\n\n"
        "Phase 1 already produced a cognition scaffold. Treat it as your working "
        "understanding of the contract. Implement `submission/featurelifted/` "
        "accordingly; refine the scaffold only if you discover a concrete error.\n\n"
        "Available probe files:\n"
        f"{probe_list}\n\n"
        "You may re-run probes or write new checks against the submission after it exists.\n\n"
        "#### Phase-1 COGNITION.md\n\n"
        f"{body}\n"
    )


def openhands_phase1_appendix() -> str:
    return phase1_task_appendix()


def openhands_phase2_appendix(*, workspace_dir: str | Path) -> str:
    workspace = Path(workspace_dir)
    cognition_path = workspace / COGNITION_FILE
    cognition_text = (
        cognition_path.read_text(encoding="utf-8") if cognition_path.is_file() else ""
    )
    probe_files: list[str] = []
    probes = workspace / PROBES_DIR
    if probes.is_dir():
        probe_files = sorted(
            str(p.relative_to(workspace))
            for p in probes.rglob("*.py")
            if p.name != "__init__.py" and p.is_file()
        )
    return phase2_task_appendix(cognition_text=cognition_text, probe_files=probe_files)


# Back-compat name used by older docs/tests.
def openhands_td_cognition_appendix() -> str:
    return phase1_task_appendix()


def validate_cognition_scaffold(workspace_dir: str | Path) -> CognitionGateResult:
    """Validate COGNITION.md schema without running probes."""

    workspace = Path(workspace_dir).resolve()
    errors: list[str] = []
    details: dict[str, Any] = {}
    cognition_path = workspace / COGNITION_FILE
    if not cognition_path.is_file():
        errors.append(f"missing {COGNITION_FILE}")
        return CognitionGateResult(False, tuple(errors), details)

    text = cognition_path.read_text(encoding="utf-8")
    details["cognition_bytes"] = len(text.encode("utf-8"))
    missing = [h for h in REQUIRED_COGNITION_HEADINGS if not _has_heading(text, h)]
    if missing:
        errors.append("missing required headings: " + ", ".join(missing))
    use_cases = _count_use_cases(text)
    details["use_case_count"] = use_cases
    if use_cases < MIN_USE_CASES:
        errors.append(
            f"need at least {MIN_USE_CASES} use cases under "
            f"'## Critical Use Cases' (found {use_cases}; "
            "accepts `1.` / `-` / `*` / `### UC1` styles)"
        )
    if _has_template_placeholders(text):
        errors.append("replace template placeholders in Critical Use Cases")
    return CognitionGateResult(not errors, tuple(errors), details)


def validate_probes(
    workspace_dir: str | Path,
    *,
    run_pytest: bool = True,
    pytest_backend: PytestBackend = "local",
    docker_image: str | None = None,
    pytest_timeout_seconds: int = DEFAULT_PROBE_PYTEST_TIMEOUT_SECONDS,
) -> CognitionGateResult:
    """Require at least one probe module and (optionally) a green pytest run."""

    workspace = Path(workspace_dir).resolve()
    errors: list[str] = []
    details: dict[str, Any] = {"pytest_backend": pytest_backend}
    probes = workspace / PROBES_DIR
    if not probes.is_dir():
        errors.append(f"missing {PROBES_DIR}/ directory")
        return CognitionGateResult(False, tuple(errors), details)

    probe_files = sorted(
        p for p in probes.rglob("*.py") if p.name != "__init__.py" and p.is_file()
    )
    details["probe_files"] = [str(p.relative_to(workspace)) for p in probe_files]
    if not probe_files:
        errors.append(
            f"no probe modules under {PROBES_DIR}/ "
            "(need at least one *.py besides __init__.py)"
        )
        return CognitionGateResult(False, tuple(errors), details)

    banned = []
    for path in probe_files:
        body = path.read_text(encoding="utf-8", errors="replace")
        if re.search(
            r"\bsubmission\.featurelifted\b|\bfrom\s+submission\b|\bimport\s+submission\b",
            body,
        ):
            banned.append(str(path.relative_to(workspace)))
    if banned:
        errors.append(
            "phase-1 probes must not import submission: " + ", ".join(banned)
        )

    if run_pytest and not errors:
        _run_probe_pytest(
            workspace,
            probes,
            errors=errors,
            details=details,
            pytest_backend=pytest_backend,
            docker_image=docker_image,
            pytest_timeout_seconds=pytest_timeout_seconds,
        )

    return CognitionGateResult(not errors, tuple(errors), details)


def evaluate_phase1_artifacts(
    workspace_dir: str | Path,
    *,
    run_pytest: bool = True,
    pytest_backend: PytestBackend = "local",
    docker_image: str | None = None,
    pytest_timeout_seconds: int = DEFAULT_PROBE_PYTEST_TIMEOUT_SECONDS,
) -> CognitionGateResult:
    """Full phase-1 quality check (recorded; phase 2 still proceeds)."""

    scaffold = validate_cognition_scaffold(workspace_dir)
    probes = validate_probes(
        workspace_dir,
        run_pytest=run_pytest,
        pytest_backend=pytest_backend,
        docker_image=docker_image,
        pytest_timeout_seconds=pytest_timeout_seconds,
    )
    errors = list(scaffold.errors) + list(probes.errors)
    details = {"scaffold": scaffold.details, "probes": probes.details}
    return CognitionGateResult(not errors, tuple(errors), details)


# Alias used in docs / plan wording.
evaluate_phase1_gate = evaluate_phase1_artifacts


def prepare_phase2_workspace(workspace_dir: str | Path, task_markdown: str) -> str:
    """Reset submission/ and rewrite TASK.md with phase-2 injection."""

    workspace = Path(workspace_dir).resolve()
    submission = workspace / "submission"
    if submission.is_file() or submission.is_symlink():
        submission.unlink()
    elif submission.is_dir():
        shutil.rmtree(submission)
    submission.mkdir(parents=True)

    # Strip any prior TD appendix blocks, then append phase-2 injection.
    base = re.sub(
        r"\n## TD-Cognition.*",
        "",
        task_markdown,
        flags=re.DOTALL,
    ).rstrip()
    appendix = openhands_phase2_appendix(workspace_dir=workspace)
    new_task = base + "\n\n## TD-Cognition Phase 2\n\n" + appendix
    (workspace / "TASK.md").write_text(new_task + "\n", encoding="utf-8")
    return new_task


def write_phase_audit(
    output_dir: str | Path,
    *,
    phase1_result: CognitionGateResult,
    phase1_agent: dict[str, Any] | None,
    phase2_agent: dict[str, Any] | None = None,
) -> Path:
    path = Path(output_dir).resolve() / PHASE_AUDIT_FILE
    payload = {
        "schema_version": "featureliftbench.td_cognition_phase.v1",
        "protocol": "two_phase",
        "phase1": {
            "gate": phase1_result.to_dict(),
            "agent": _compact_agent(phase1_agent),
        },
        "phase2": {
            "agent": _compact_agent(phase2_agent),
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run_probe_pytest(
    workspace: Path,
    probes: Path,
    *,
    errors: list[str],
    details: dict[str, Any],
    pytest_backend: PytestBackend,
    docker_image: str | None,
    pytest_timeout_seconds: int,
) -> None:
    if pytest_backend == "docker":
        from .agent_docker import DEFAULT_AGENT_IMAGE
        from .agent_docker import run_command_in_agent_docker

        image = (docker_image or "").strip() or DEFAULT_AGENT_IMAGE
        details["docker_image"] = image
        result = run_command_in_agent_docker(
            workspace,
            ["python", "-m", "pytest", f"{PROBES_DIR}/", "-q", "--tb=no"],
            image=image,
            timeout_seconds=pytest_timeout_seconds,
        )
        details["pytest_returncode"] = result.returncode
        details["pytest_stdout_tail"] = (result.stdout or "")[-2000:]
        details["pytest_stderr_tail"] = (result.stderr or "")[-2000:]
        details["pytest_timed_out"] = result.timed_out
        if result.returncode != 0:
            errors.append(
                f"pytest {PROBES_DIR}/ failed (exit {result.returncode}"
                f"{', timed_out' if result.timed_out else ''}); "
                "probes must pass without submission/ "
                f"(backend=docker image={image})"
            )
        return

    # local backend
    details["docker_image"] = None
    probe = subprocess.run(
        [sys.executable, "-c", "import pytest"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        errors.append(
            "local pytest unavailable on host interpreter "
            f"({sys.executable}); install pytest or run the Phase-1 gate "
            "with pytest_backend='docker'"
        )
        details["pytest_returncode"] = probe.returncode
        details["pytest_stderr_tail"] = (probe.stderr or "")[-2000:]
        return

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(probes), "-q", "--tb=no"],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        check=False,
        timeout=max(1, int(pytest_timeout_seconds)),
    )
    details["pytest_returncode"] = proc.returncode
    details["pytest_stdout_tail"] = (proc.stdout or "")[-2000:]
    details["pytest_stderr_tail"] = (proc.stderr or "")[-2000:]
    if proc.returncode != 0:
        errors.append(
            f"pytest {PROBES_DIR}/ failed (exit {proc.returncode}); "
            "probes must pass without submission/ (backend=local)"
        )


def _compact_agent(agent: dict[str, Any] | None) -> dict[str, Any] | None:
    if not agent:
        return None
    keep = (
        "name",
        "passed",
        "returncode",
        "duration_seconds",
        "timed_out",
        "reason",
        "resource_limited",
    )
    return {k: agent.get(k) for k in keep}


def _normalize_heading(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _has_heading(text: str, canonical: str) -> bool:
    if canonical in text:
        return True
    aliases = _HEADING_ALIASES.get(canonical, ())
    for match in re.finditer(r"(?m)^##\s+(.+?)\s*$", text):
        title = _normalize_heading(match.group(1))
        for alias in aliases:
            if title == _normalize_heading(alias):
                return True
    return False


def _use_case_section(text: str) -> str | None:
    match = re.search(
        r"(?im)^##\s+[^\n]*use[^\n]*cases?[^\n]*\s*\n(.*?)(?=\n##\s+|\Z)",
        text,
        flags=re.DOTALL,
    )
    return match.group(1) if match else None


def _count_use_cases(text: str) -> int:
    section = _use_case_section(text)
    if section is None:
        return 0
    patterns = (
        r"(?m)^\s*\d+\.\s+\S+",  # 1. ...
        r"(?m)^\s*[-*]\s+\S+",  # - ... / * ...
        r"(?m)^\s*#{3,6}\s*UC\s*\d+\b",  # ### UC1
        r"(?m)^\s*#{3,6}\s*Use\s*Case\s*\d+\b",  # ### Use Case 1
    )
    found: set[str] = set()
    for pattern in patterns:
        for hit in re.finditer(pattern, section, flags=re.IGNORECASE):
            found.add(hit.group(0).strip().lower())
    return len(found)


def _has_template_placeholders(text: str) -> bool:
    section = _use_case_section(text)
    if section is None:
        return False
    # Fail when starter numbered lines still look like the seeded template.
    empty_numbered = re.findall(
        r"(?m)^\s*\d+\.\s+(?:\.\.\.|…|\(precondition\))",
        section,
    )
    return len(empty_numbered) >= 3
