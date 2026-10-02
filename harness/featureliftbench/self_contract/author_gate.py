"""Author-gate: enough real tests; empty stub must fail contracts."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from ..exec_contract.verify import verify_submission_contracts
from .common import CONTRACTS_DIR
from .common import DEFAULT_MIN_TESTS


_ASSERT_TRUE_RE = re.compile(r"\bassert\s+True\b")
_TEST_DEF_RE = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.MULTILINE)


def _count_tests(contracts: Path) -> list[str]:
    names: list[str] = []
    for path in sorted(contracts.rglob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        names.extend(_TEST_DEF_RE.findall(text))
    return names


def _has_assert_true(contracts: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(contracts.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if _ASSERT_TRUE_RE.search(text):
            hits.append(path.relative_to(contracts).as_posix())
    return hits


def _install_empty_stub(submission: Path) -> None:
    if submission.exists():
        shutil.rmtree(submission)
    pkg = submission / "featurelifted"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        '"""Intentionally empty stub for author-gate (must fail real contracts)."""\n',
        encoding="utf-8",
    )


def evaluate_author_gate(
    workspace_dir: str | Path,
    *,
    docker_image: str | None = None,
    use_docker: bool = True,
    min_tests: int = DEFAULT_MIN_TESTS,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    contracts = workspace / CONTRACTS_DIR
    errors: list[str] = []
    test_names = _count_tests(contracts) if contracts.is_dir() else []
    if len(test_names) < int(min_tests):
        errors.append(
            f"need at least {min_tests} test_* functions, found {len(test_names)}"
        )
    true_hits = _has_assert_true(contracts) if contracts.is_dir() else []
    if true_hits:
        errors.append(f"forbidden assert True in: {', '.join(true_hits[:8])}")

    submission = workspace / "submission"
    # Preserve any author-phase submission aside; gate uses a fresh empty stub.
    backup = workspace / ".submission_author_backup"
    if backup.exists():
        shutil.rmtree(backup)
    if submission.exists():
        shutil.move(str(submission), str(backup))
    _install_empty_stub(submission)

    stub_verify = verify_submission_contracts(
        workspace,
        docker_image=docker_image,
        use_docker=use_docker,
    )
    # Empty stub must NOT pass real contracts.
    if stub_verify.get("ok"):
        errors.append(
            "contracts passed against empty featurelifted stub (vacuous / too weak)"
        )
    elif stub_verify.get("error") and "missing" in str(stub_verify.get("error")):
        errors.append(str(stub_verify.get("error")))
    else:
        combined = (
            f"{stub_verify.get('stdout_tail') or ''}\n"
            f"{stub_verify.get('stderr_tail') or ''}"
        ).lower()
        if "collected 0 items" in combined or "no tests ran" in combined:
            errors.append(
                "contracts collected 0 runnable tests against empty stub "
                "(collection/skip-only — too weak)"
            )

    # Restore author submission backup if any (will be wiped before implement anyway).
    shutil.rmtree(submission, ignore_errors=True)
    if backup.exists():
        shutil.move(str(backup), str(submission))
    else:
        submission.mkdir(parents=True, exist_ok=True)

    ok = not errors
    return {
        "ok": ok,
        "errors": errors,
        "test_names": test_names,
        "test_count": len(test_names),
        "min_tests": int(min_tests),
        "assert_true_files": true_hits,
        "stub_verify": stub_verify,
    }
