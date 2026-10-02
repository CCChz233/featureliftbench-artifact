"""Evidence-backed validation gate for complete benchmark suites.

The gate is deliberately read-only.  Mechanical checks produce facts, API
reviewers may add semantic evidence, and only explicit adjudications can turn
pending semantic findings into confirmed failures or false positives.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .catalog import get_suite, load_catalog
from .constitution_validate import _validate_task_leakage
from .paths import REPO_ROOT
from .source_archive import (
    load_source_registry,
    materialize_snapshot,
    sha256_file,
    source_indexes,
)
from .validate import validate_task


GATE_VERSION = "featureliftbench.benchmark_gate.v2.p0"
PROMPT_VERSION = "featureliftbench.benchmark_validator_api.v1"
AGENT_PROMPT_VERSION = "featureliftbench.benchmark_validator_agent.v2.3"

PASS = "pass"
FAIL = "fail"
UNDETERMINED = "undetermined"

MEETS = "meets_standard"
VIOLATES = "violates"

ADJUDICATION_VERDICTS = {
    "confirmed_violation",
    "false_positive",
    "insufficient_evidence",
}

DEFAULT_ORACLE_SUMMARY = (
    REPO_ROOT
    / "reports"
    / "audits"
    / "python200_prime_oracle_revalidation"
    / "summary.json"
)

DEFAULT_UPSTREAM_DIRECT_SUMMARY = (
    REPO_ROOT
    / "reports"
    / "audits"
    / "python200_prime_g2prime"
    / "summary.json"
)


@dataclass(frozen=True)
class ReviewerConfig:
    """OpenAI-compatible reviewer configuration without persisted secrets."""

    model: str
    api_base: str
    api_key: str
    timeout_seconds: int = 180
    max_hidden_chars: int = 100_000
    max_source_chars: int = 80_000
    max_output_tokens: int = 4_096
    reasoning_effort: str = "low"
    mode: str = "one_shot"
    agent_max_turns: int = 6
    agent_max_total_tokens: int = 40_000
    agent_max_context_chars: int = 60_000
    agent_max_nodeids_per_turn: int = 4
    agent_max_symbols_per_turn: int = 4
    agent_tool_result_chars: int = 16_000
    agent_pending_only: bool = True

    @property
    def endpoint(self) -> str:
        base = self.api_base.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    @property
    def public_endpoint_id(self) -> str:
        parsed = urllib.parse.urlsplit(self.api_base)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


class ReviewerResponseError(ValueError):
    """A response arrived but did not contain a usable JSON action."""

    def __init__(
        self,
        message: str,
        *,
        usage: dict[str, Any],
        finish_reason: str,
        content_chars: int,
        reasoning_chars: int,
    ) -> None:
        super().__init__(message)
        self.usage = usage
        self.finish_reason = finish_reason
        self.content_chars = content_chars
        self.reasoning_chars = reasoning_chars


@dataclass
class GateRunOptions:
    benchmark: str = "python200_hard"
    output: Path | None = None
    task_ids: tuple[str, ...] = ()
    source_materialization: bool = True
    oracle_summary: Path | None = DEFAULT_ORACLE_SUMMARY
    upstream_direct_summary: Path | None = DEFAULT_UPSTREAM_DIRECT_SUMMARY
    adjudications: Path | None = None
    reviewer: ReviewerConfig | None = None
    private_evaluator_policy_acknowledged: bool = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value))


def _sha256_tree(root: Path, *, excluded_top: set[str] | None = None) -> str:
    """Hash task-owned inputs while leaving canonical source to its own digest."""

    excluded = excluded_top or set()
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().encode()):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in excluded:
            continue
        if not path.is_file() or path.is_symlink():
            continue
        rel = relative.as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(rel + b"\0" + str(len(content)).encode() + b"\0")
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _check(
    status: str,
    *,
    blocking: bool,
    evidence: Iterable[Any] = (),
    reason: str = "",
    mechanical_result: str = "clear",
    adjudication: str = "not_needed",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in {PASS, FAIL, UNDETERMINED}:
        raise ValueError(f"invalid gate status: {status}")
    row: dict[str, Any] = {
        "status": status,
        "blocking": blocking,
        "mechanical_result": mechanical_result,
        "adjudication": adjudication,
        "reason": reason,
        "evidence": list(evidence),
    }
    if details:
        row["details"] = details
    return row


def aggregate_label(checks: dict[str, dict[str, Any]]) -> str:
    """Aggregate only blocking checks using confirmed-fail-first semantics."""

    blocking = [row for row in checks.values() if row.get("blocking")]
    if any(row.get("status") == FAIL for row in blocking):
        return VIOLATES
    if any(row.get("status") == UNDETERMINED for row in blocking):
        return UNDETERMINED
    return MEETS


def load_adjudications(path: Path | None) -> dict[tuple[str, str], dict[str, str]]:
    if path is None:
        return {}
    if not path.is_file():
        raise ValueError(f"adjudications file missing: {path}")
    rows: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            task_id = (raw.get("task_id") or "").strip()
            rule = (raw.get("rule") or "").strip()
            verdict = (raw.get("verdict") or "").strip()
            if not task_id or not rule:
                raise ValueError("adjudication requires task_id and rule")
            if verdict not in ADJUDICATION_VERDICTS:
                raise ValueError(
                    f"invalid adjudication verdict {verdict!r} for {task_id}/{rule}"
                )
            key = (task_id, rule)
            if key in rows:
                raise ValueError(f"duplicate adjudication: {task_id}/{rule}")
            rows[key] = {str(k): str(v or "") for k, v in raw.items() if k}
    return rows


def _apply_pending_finding(
    *,
    task_id: str,
    rule: str,
    evidence: list[Any],
    blocking: bool,
    adjudications: dict[tuple[str, str], dict[str, str]],
    reason: str,
) -> dict[str, Any]:
    record = adjudications.get((task_id, rule))
    if record is None:
        return _check(
            UNDETERMINED,
            blocking=blocking,
            evidence=evidence,
            reason=reason,
            mechanical_result="hit",
            adjudication="pending",
        )
    verdict = record["verdict"]
    adjudication_evidence = {
        "verdict": verdict,
        "rationale": record.get("rationale") or record.get("reason") or "",
        "provenance": record.get("provenance") or "",
    }
    if verdict == "confirmed_violation":
        return _check(
            FAIL,
            blocking=blocking,
            evidence=[*evidence, adjudication_evidence],
            reason="mechanical finding confirmed by adjudication",
            mechanical_result="hit",
            adjudication=verdict,
        )
    if verdict == "false_positive":
        return _check(
            PASS,
            blocking=blocking,
            evidence=[*evidence, adjudication_evidence],
            reason="mechanical finding overturned by adjudication",
            mechanical_result="hit",
            adjudication=verdict,
        )
    return _check(
        UNDETERMINED,
        blocking=blocking,
        evidence=[*evidence, adjudication_evidence],
        reason="adjudication found insufficient evidence",
        mechanical_result="hit",
        adjudication=verdict,
    )


@lru_cache(maxsize=4)
def _load_repo_script(name: str) -> Any:
    """Reuse repository audit implementations without copying their visitors."""

    path = REPO_ROOT / "harness" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_flb_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load audit module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _surface_check(
    task_dir: Path,
    public_spec: dict[str, Any],
    adjudications: dict[tuple[str, str], dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rule = "L2_C1_SURFACE"
    hidden = task_dir / "hidden_tests"
    if not hidden.is_dir():
        return _check(
            UNDETERMINED,
            blocking=True,
            reason="hidden_tests directory missing",
            mechanical_result="error",
        ), []
    parse_errors: list[str] = []
    for path in sorted(hidden.rglob("*.py")):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError) as exc:
            parse_errors.append(f"{path.relative_to(task_dir)}: {exc}")
    if parse_errors:
        return _check(
            UNDETERMINED,
            blocking=True,
            evidence=parse_errors,
            reason="C1 could not parse all hidden tests",
            mechanical_result="error",
        ), []

    audit = _load_repo_script("audit_contract_entailment")
    contract = audit.Contract(public_spec)
    by_member: dict[str, list[str]] = defaultdict(list)
    for path in sorted(hidden.rglob("*.py")):
        if path.name == audit.SURFACE_TEST_FILE:
            continue
        used = audit.members_used_in_source(path.read_text(encoding="utf-8"), contract)
        for member in used:
            if member.split(".")[0] in contract.tops and member not in contract.members:
                by_member[member].append(path.relative_to(task_dir).as_posix())
    if not by_member:
        return _check(PASS, blocking=True, reason="no undeclared exercised members"), []

    evidence = [
        {"member": member, "hidden_files": sorted(paths)}
        for member, paths in sorted(by_member.items())
    ]
    check = _apply_pending_finding(
        task_id=task_dir.name,
        rule=rule,
        evidence=evidence,
        blocking=True,
        adjudications=adjudications,
        reason="C1 found hidden members absent from required_api; adjudication required",
    )
    findings = [
        {
            "task_id": task_dir.name,
            "rule": rule,
            "kind": "undeclared_surface",
            **item,
        }
        for item in evidence
    ]
    return check, findings


def _entrypoints(metadata: dict[str, Any]) -> list[str]:
    public = metadata.get("public_spec") or {}
    feature = metadata.get("feature") or {}
    raw = public.get("source_entrypoints") or feature.get("source_entrypoints") or []
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _entrypoint_check(
    task_id: str,
    metadata: dict[str, Any],
    source_root: Path | None,
    adjudications: dict[tuple[str, str], dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]], Any | None]:
    rule = "L2_C2_ENTRYPOINT"
    declared = _entrypoints(metadata)
    if not declared:
        return _check(
            UNDETERMINED,
            blocking=True,
            reason="no maintainer source_entrypoints declared",
            mechanical_result="error",
        ), [], None
    if source_root is None:
        return _check(
            UNDETERMINED,
            blocking=True,
            evidence=declared,
            reason="canonical source was not materialized",
            mechanical_result="error",
        ), [], None

    audit = _load_repo_script("audit_source_entrypoints")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            snapshot = audit.Snapshot(source_root)
        entries = [
            {"symbol": symbol, "verdict": snapshot.resolve(symbol)}
            for symbol in declared
        ]
    except Exception as exc:  # pragma: no cover - defensive around arbitrary source
        return _check(
            UNDETERMINED,
            blocking=True,
            evidence=[str(exc)],
            reason="C2 canonical source indexing failed",
            mechanical_result="error",
        ), [], None

    undecidable = [item for item in entries if item["verdict"] == "undecidable"]
    dangling = [item for item in entries if item["verdict"] == "dangling"]
    findings = [
        {
            "task_id": task_id,
            "rule": rule,
            "kind": "entrypoint_" + item["verdict"],
            **item,
        }
        for item in entries
        if item["verdict"] in {"dangling", "misplaced", "undecidable"}
    ]
    if undecidable:
        return _check(
            UNDETERMINED,
            blocking=True,
            evidence=entries,
            reason="one or more entrypoints are undecidable",
            mechanical_result="error",
            details={"parse_failures": snapshot.parse_failures},
        ), findings, snapshot
    if dangling:
        check = _apply_pending_finding(
            task_id=task_id,
            rule=rule,
            evidence=entries,
            blocking=True,
            adjudications=adjudications,
            reason="C2 found dangling entrypoints; adjudication required",
        )
        return check, findings, snapshot
    return _check(
        PASS,
        blocking=True,
        evidence=entries,
        reason="all entrypoints resolve or are conservatively misplaced",
        details={"parse_failures": snapshot.parse_failures},
    ), findings, snapshot


class _NormalizeTests(ast.NodeTransformer):
    """Erase incidental naming, keep everything that carries a test's meaning.

    Local identifiers and parameter names are incidental: the same assertion
    reads the same whether the variable is ``aliases`` or ``a``. Three things
    are not incidental and are kept verbatim:

    - **Literals.** An earlier revision replaced every literal with a type
      marker, which collapsed distinct parameterizations of one API call and
      produced 29/200 advisory hits on Python-200', all false positives (two
      ``croniter`` cases differing only in the cron expression and the expected
      datetime, for example).
    - **Imported symbols.** The subject under test arrives by import, so
      collapsing it hides the difference between ``validate(...)`` and
      ``compact(...)``, or between ``CamelPerson`` and ``CamelFieldPerson``.
    - **Attribute names**, since the member being asserted on is the point.
    """

    def __init__(self, significant: frozenset[str] = frozenset()) -> None:
        super().__init__()
        self._significant = significant

    def visit_Name(self, node: ast.Name) -> ast.AST:  # noqa: N802
        if node.id in self._significant:
            return node
        return ast.copy_location(ast.Name(id="_NAME", ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg) -> ast.AST:  # noqa: N802
        return ast.copy_location(ast.arg(arg="_ARG", annotation=None), node)


def _significant_names(tree: ast.Module) -> frozenset[str]:
    """Named subjects in a test module, as opposed to incidental locals.

    Imported symbols are the API under test. Module-level classes and helpers
    are fixtures the tests are built around, and their names distinguish
    otherwise identical bodies: ``CamelPerson`` and ``CamelFieldPerson`` differ
    only in their decorators, so a body-only comparison would collapse
    class-level and field-level letter casing onto one shape.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("test"):
                names.add(node.name)
    return frozenset(names)


def _strip_docstring(node: ast.AST) -> None:
    """Drop a leading string expression from every body that can carry one."""
    for child in ast.walk(node):
        body = getattr(child, "body", None)
        if not isinstance(body, list) or not body:
            continue
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            del body[0]


def _normalized_test_shapes(root: Path) -> tuple[set[str], list[str]]:
    """Normalize complete test bodies, not isolated ubiquitous assertions."""

    shapes: set[str] = set()
    errors: list[str] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        significant = _significant_names(tree)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            node.name = "_TEST"
            node.decorator_list = []
            _strip_docstring(node)
            normalized = _NormalizeTests(significant).visit(
                ast.fix_missing_locations(node)
            )
            shapes.add(ast.dump(normalized, include_attributes=False))
    return shapes, errors


def _overlap_check(task_dir: Path) -> dict[str, Any]:
    public, public_errors = _normalized_test_shapes(task_dir / "public_tests")
    hidden, hidden_errors = _normalized_test_shapes(task_dir / "hidden_tests")
    if public_errors or hidden_errors:
        return _check(
            UNDETERMINED,
            blocking=False,
            evidence=[*public_errors, *hidden_errors],
            reason="C4 could not parse all tests",
            mechanical_result="error",
        )
    overlap = public & hidden
    denominator = max(1, min(len(public), len(hidden)))
    ratio = len(overlap) / denominator
    return _check(
        PASS if not overlap else UNDETERMINED,
        blocking=False,
        evidence=[{"normalized_test_overlap": len(overlap), "ratio": ratio}],
        reason=(
            "no normalized whole-test overlap"
            if not overlap
            else "normalized whole-test overlap is advisory pending threshold calibration"
        ),
        mechanical_result="clear" if not overlap else "hit",
        adjudication="not_needed" if not overlap else "pending",
        details={
            "public_test_shapes": len(public),
            "hidden_test_shapes": len(hidden),
            "overlap": len(overlap),
            "overlap_ratio": ratio,
        },
    )


def _load_oracle_evidence(path: Path | None) -> tuple[dict[str, list[dict[str, Any]]], str]:
    if path is None or not path.is_file():
        return {}, ""
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload.get("runs") or []:
        task_id = str(row.get("task_id") or "")
        if task_id:
            by_task[task_id].append(row)
    return dict(by_task), sha256_file(path)


def _load_upstream_direct_evidence(
    path: Path | None,
) -> tuple[dict[str, dict[str, Any]], str]:
    if path is None or not path.is_file():
        return {}, ""
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_task: dict[str, dict[str, Any]] = {}
    for row in payload.get("records") or []:
        task_id = str(row.get("task_id") or "")
        if task_id:
            by_task[task_id] = row
    return by_task, sha256_file(path)


def _upstream_direct_check(task_id: str, record: dict[str, Any] | None) -> dict[str, Any]:
    """G2' — the pinned upstream, submitted directly, must not satisfy the contract.

    Evidence strength is carried through rather than flattened. Most tasks are
    cleared because the isolation layer refuses an upstream import before any
    behavior runs; that is a real property of the harness but it is not evidence
    about the task's contract, so the check records which mechanism applied.
    """
    if not record:
        return _check(
            UNDETERMINED,
            blocking=True,
            reason="task is not covered by the upstream-direct audit",
            mechanical_result="error",
        )
    status = str(record.get("status") or "")
    outcome = record.get("outcome") or {}
    evidence = [{
        "evidence_strength": record.get("evidence_strength"),
        "block_mechanism": record.get("block_mechanism"),
        "first_block": record.get("first_block"),
        "functional_gate": outcome.get("functional_gate"),
        "stubbed_names": record.get("stubbed_names") or [],
        "errors": outcome.get("errors") or [],
    }]
    if status == "fail":
        return _check(
            FAIL,
            blocking=True,
            evidence=evidence,
            reason="the pinned upstream, submitted directly, satisfies the contract",
            mechanical_result="hit",
            adjudication="confirmed_violation",
        )
    if status == "pass":
        return _check(
            PASS,
            blocking=True,
            evidence=evidence,
            reason=str(record.get("reason") or "upstream-direct submission does not pass"),
        )
    return _check(
        UNDETERMINED,
        blocking=True,
        evidence=evidence,
        reason=str(record.get("reason") or "upstream-direct audit was inconclusive"),
        mechanical_result="error",
    )


_ISOLATION_FLAGS = (
    "pass",
    "forbidden_imports_pass",
    "forbidden_dependencies_pass",
    "forbidden_runtime_capabilities_pass",
    "runtime_import_origin_pass",
    "source_filesystem_absent",
    "network_disabled",
    "submission_location_pass",
    "mount_allowlist_pass",
)
_SANDBOX_EXPECTED = {
    "backend": "docker",
    "network": "none",
    "read_only_rootfs": True,
    "cap_drop": "ALL",
    "returncode": 0,
}
_VERIFICATION_MODE = "docker_functional_capsule_v1"


def _isolation_check(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """L4 — surface the sandbox contract per task instead of implying it.

    The evaluator already enforces these flags on every run, but the gate ledger
    has to be diffable: "was this task still evaluated under no-network,
    read-only, source-absent conditions" must be answerable from the report
    rather than by re-reading the evaluator. Evidence comes from the same N=3
    oracle revalidation the oracle check consumes.
    """
    if not runs:
        return _check(
            UNDETERMINED,
            blocking=True,
            reason="task is not covered by an isolation-bearing evaluation",
            mechanical_result="error",
        )
    violations: list[str] = []
    for row in runs:
        result = row.get("result") or {}
        isolation = result.get("isolation") or {}
        sandbox = result.get("sandbox") or {}
        repetition = row.get("repetition")
        if not isolation and not sandbox:
            violations.append(f"r{repetition}: no isolation or sandbox record")
            continue
        for flag in _ISOLATION_FLAGS:
            if isolation.get(flag) is not True:
                violations.append(f"r{repetition}: isolation.{flag}={isolation.get(flag)!r}")
        if isolation.get("verification_mode") != _VERIFICATION_MODE:
            violations.append(
                f"r{repetition}: verification_mode="
                f"{isolation.get('verification_mode')!r}"
            )
        for key, expected in _SANDBOX_EXPECTED.items():
            if sandbox.get(key) != expected:
                violations.append(f"r{repetition}: sandbox.{key}={sandbox.get(key)!r}")
    evidence = [{
        "repetitions": sorted(row.get("repetition") for row in runs),
        "violations": violations[:12],
    }]
    if violations:
        return _check(
            FAIL,
            blocking=True,
            evidence=evidence,
            reason="evaluation did not hold the declared isolation contract",
            mechanical_result="hit",
            adjudication="confirmed_violation",
        )
    return _check(
        PASS,
        blocking=True,
        evidence=evidence,
        reason=(
            f"isolation contract held on all {len(runs)} repetitions "
            f"({_VERIFICATION_MODE})"
        ),
    )


def _leakage_check(task_dir: Path) -> dict[str, Any]:
    """L5 — private evaluator assets must not reach the Agent-facing TASK.md.

    ``validate_constitution`` already applies these rules, but only for tasks
    whose ``spec_status`` is ``compliant``, and the result is folded into
    ``L1_PACKAGE``. Running them unconditionally as their own row makes the
    coverage explicit and keeps a non-compliant task from silently skipping it.
    """
    try:
        metadata = json.loads((task_dir / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _check(
            UNDETERMINED,
            blocking=True,
            reason=f"metadata is unreadable for the leakage rules: {exc}",
            mechanical_result="error",
        )
    if not (task_dir / "TASK.md").is_file():
        return _check(
            FAIL,
            blocking=True,
            reason="TASK.md is missing, so the Agent-facing surface cannot be audited",
            mechanical_result="hit",
            adjudication="confirmed_violation",
        )
    try:
        errors = _validate_task_leakage(task_dir, metadata)
    except (OSError, ValueError) as exc:
        return _check(
            UNDETERMINED,
            blocking=True,
            reason=f"leakage rules could not be applied: {type(exc).__name__}: {exc}",
            mechanical_result="error",
        )
    if errors:
        return _check(
            FAIL,
            blocking=True,
            evidence=errors,
            reason="TASK.md exposes a private evaluator asset",
            mechanical_result="hit",
            adjudication="confirmed_violation",
        )
    return _check(
        PASS,
        blocking=True,
        reason="TASK.md does not mention hidden tests, evaluation_spec, "
        "oracle_manifest, or private metadata keys",
    )


def _oracle_check(
    task_id: str,
    runs: list[dict[str, Any]],
    source_digest: str,
) -> dict[str, Any]:
    if not runs:
        return _check(
            UNDETERMINED,
            blocking=True,
            reason="task is not covered by oracle revalidation",
            mechanical_result="error",
        )
    passed = [bool(row.get("passed")) for row in runs]
    fingerprints = {str(row.get("fingerprint") or "") for row in runs}
    source_digests = {
        str(((row.get("result") or {}).get("source") or {}).get("source_digest") or "")
        for row in runs
    }
    evidence = [{
        "repetitions": sorted(row.get("repetition") for row in runs),
        "passed": passed,
        "fingerprints": sorted(fingerprints),
        "source_digests": sorted(source_digests),
    }]
    if any(not value for value in passed):
        return _check(
            FAIL,
            blocking=True,
            evidence=evidence,
            reason="oracle revalidation contains a failed run",
            mechanical_result="hit",
            adjudication="confirmed_violation",
        )
    if len(runs) < 3 or len(fingerprints) != 1 or "" in fingerprints:
        return _check(
            UNDETERMINED,
            blocking=True,
            evidence=evidence,
            reason="oracle evidence is not a stable N=3 fingerprint",
            mechanical_result="error",
        )
    if source_digest and source_digests != {source_digest}:
        return _check(
            UNDETERMINED,
            blocking=True,
            evidence=evidence,
            reason="oracle source digest does not match the current registry",
            mechanical_result="error",
        )
    return _check(
        PASS,
        blocking=True,
        evidence=evidence,
        reason="oracle passes with stable N=3 fingerprint",
    )


class CanonicalSourceWorkspace:
    """Materialize each verified source snapshot at most once per gate run."""

    def __init__(self, registry_path: Path, *, materialize: bool) -> None:
        self.registry_path = registry_path
        self.registry = load_source_registry(registry_path)
        _, self.task_snapshots = source_indexes(self.registry)
        self.materialize = materialize
        self._temporary = tempfile.TemporaryDirectory(prefix="flb-benchmark-gate-")
        self._roots: dict[str, Path] = {}
        self._errors: dict[str, str] = {}

    def close(self) -> None:
        self._temporary.cleanup()

    def identity(self, task_id: str) -> tuple[dict[str, Any], Path | None, str | None]:
        snapshot = self.task_snapshots.get(task_id)
        if snapshot is None:
            return {}, None, "task has no canonical source registry mapping"
        identity = {
            key: snapshot.get(key)
            for key in (
                "source_repo_id",
                "source_snapshot_id",
                "resolved_commit",
                "source_tree_sha256",
                "archive_sha256",
                "current_snapshot_scope",
                "status",
            )
        }
        snapshot_id = str(snapshot.get("source_snapshot_id") or "")
        archive_raw = str(snapshot.get("archive_path") or "")
        archive = Path(archive_raw)
        if not archive.is_absolute():
            archive = REPO_ROOT / archive
        if not archive.is_file():
            return identity, None, f"canonical archive missing: {archive}"
        expected_archive = str(snapshot.get("archive_sha256") or "")
        actual_archive = sha256_file(archive)
        if not expected_archive or actual_archive != expected_archive:
            return identity, None, "canonical archive SHA-256 mismatch"
        if not self.materialize:
            return identity, None, None
        if snapshot_id in self._errors:
            return identity, None, self._errors[snapshot_id]
        if snapshot_id not in self._roots:
            destination = Path(self._temporary.name) / snapshot_id
            try:
                materialize_snapshot(snapshot, destination, root=REPO_ROOT)
            except (OSError, ValueError) as exc:
                self._errors[snapshot_id] = str(exc)
                return identity, None, str(exc)
            self._roots[snapshot_id] = destination
        return identity, self._roots[snapshot_id], None


def _source_check(identity: dict[str, Any], error: str | None, materialized: bool) -> dict[str, Any]:
    if error:
        return _check(
            UNDETERMINED,
            blocking=True,
            evidence=[identity, error],
            reason="canonical source identity could not be verified",
            mechanical_result="error",
        )
    if identity.get("status") != "ready" or identity.get("current_snapshot_scope") != "full_tracked_tree":
        return _check(
            FAIL,
            blocking=True,
            evidence=[identity],
            reason="canonical source is not a ready full tracked tree",
            mechanical_result="hit",
            adjudication="confirmed_violation",
        )
    return _check(
        PASS,
        blocking=True,
        evidence=[identity],
        reason=(
            "canonical archive and source tree verified"
            if materialized
            else "canonical archive verified; source tree materialization skipped"
        ),
    )


def _hidden_payload(task_dir: Path, limit: int) -> tuple[dict[str, str], bool]:
    payload: dict[str, str] = {}
    used = 0
    truncated = False
    for path in sorted((task_dir / "hidden_tests").rglob("*.py")):
        content = path.read_text(encoding="utf-8")
        remaining = limit - used
        if remaining <= 0:
            truncated = True
            break
        if len(content) > remaining:
            payload[path.relative_to(task_dir).as_posix()] = content[:remaining]
            truncated = True
            break
        payload[path.relative_to(task_dir).as_posix()] = content
        used += len(content)
    return payload, truncated


def _source_evidence(
    source_root: Path,
    snapshot: Any | None,
    entrypoints: list[str],
    limit: int,
) -> tuple[dict[str, str], bool]:
    candidates: list[Path] = []
    if snapshot is not None:
        for symbol in entrypoints:
            found = snapshot.longest_module_prefix(symbol)
            if found is not None:
                path = snapshot.modules.get(found[0])
                if path is not None and path not in candidates:
                    candidates.append(path)
    leaves = {item.split(".")[-1] for item in entrypoints}
    for path in sorted(source_root.rglob("*")):
        if len(candidates) >= 8:
            break
        if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".rst"}:
            continue
        if path in candidates:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(re.search(rf"\b{re.escape(leaf)}\b", text) for leaf in leaves if leaf):
            candidates.append(path)

    result: dict[str, str] = {}
    used = 0
    per_file_limit = max(4_000, limit // max(1, len(candidates)))
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="replace")
        remaining = limit - used
        if remaining <= 0:
            break
        excerpt = _bounded_source_excerpt(
            text,
            leaves=leaves,
            limit=min(remaining, per_file_limit),
        )
        if not excerpt:
            continue
        result[path.relative_to(source_root).as_posix()] = excerpt
        used += len(excerpt)
    # Source packets intentionally contain symbol-focused excerpts rather than
    # complete repositories.  This flag only reports an unusable packet; the
    # excerpt markers themselves make the bounded nature explicit to reviewers.
    return result, not bool(result)


def _bounded_source_excerpt(text: str, *, leaves: set[str], limit: int) -> str:
    """Return auditable, line-numbered excerpts around declared entrypoint symbols."""

    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text

    lines = text.splitlines(keepends=True)
    definition_patterns = [
        re.compile(rf"^\s*(?:async\s+def|def|class)\s+{re.escape(leaf)}\b")
        for leaf in sorted(leaves)
        if leaf
    ]
    hit_lines = [
        index
        for index, line in enumerate(lines)
        if any(pattern.search(line) for pattern in definition_patterns)
    ]
    if not hit_lines:
        reference_patterns = [
            re.compile(rf"\b{re.escape(leaf)}\b")
            for leaf in sorted(leaves)
            if leaf
        ]
        hit_lines = [
            index
            for index, line in enumerate(lines)
            if any(pattern.search(line) for pattern in reference_patterns)
        ][:4]
    if not hit_lines:
        hit_lines = [0]

    windows: list[tuple[int, int]] = []
    for index in hit_lines[:6]:
        start = max(0, index - 20)
        end = min(len(lines), index + 100)
        if windows and start <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))

    chunks: list[str] = []
    used = 0
    for start, end in windows:
        marker = f"# [canonical source excerpt: lines {start + 1}-{end}]\n"
        body = "".join(
            f"{line_number:06d}: {line}"
            for line_number, line in enumerate(lines[start:end], start=start + 1)
        )
        chunk = marker + body
        remaining = limit - used
        if remaining <= 0:
            break
        chunks.append(chunk[:remaining])
        used += min(len(chunk), remaining)
    return "".join(chunks)


def _canonical_path_for_symbol(
    source_root: Path,
    snapshot: Any | None,
    symbol: str,
) -> str | None:
    if snapshot is None:
        return None
    found = snapshot.longest_module_prefix(symbol)
    if found is None:
        return None
    path = snapshot.modules.get(found[0])
    if path is None:
        return None
    try:
        return path.relative_to(source_root).as_posix()
    except ValueError:
        return None


def _mapped_nodeids(metadata: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    evaluation = metadata.get("evaluation_spec") or {}
    for key in ("public_test_mappings", "hidden_test_mappings"):
        for row in evaluation.get(key) or []:
            if isinstance(row, dict) and row.get("nodeid"):
                result.add(str(row["nodeid"]))
    return result


def _behavior_ids(public_spec: dict[str, Any]) -> set[str]:
    return {
        str(row.get("id") or row.get("behavior_id"))
        for row in public_spec.get("behaviors") or []
        if isinstance(row, dict) and (row.get("id") or row.get("behavior_id"))
    }


def _required_api_paths(public_spec: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for row in public_spec.get("required_api") or []:
        if not isinstance(row, dict):
            continue
        if row.get("path"):
            paths.add(str(row["path"]))
        for member in row.get("members") or []:
            if isinstance(member, dict) and member.get("path"):
                paths.add(str(member["path"]))
    return paths


def _alias_api_paths(paths: Iterable[str]) -> set[str]:
    """Accept both bare members and ``featurelifted.``-prefixed citations."""

    out: set[str] = set()
    for raw in paths:
        path = str(raw).strip()
        if not path:
            continue
        out.add(path)
        if path.startswith("featurelifted."):
            out.add(path[len("featurelifted.") :])
        else:
            out.add(f"featurelifted.{path}")
    return out


CANONICAL_SOURCE_ROLE = (
    "canonical pinned upstream of this task; this is the implementation to audit. "
    "There is no separate featurelifted/ source tree."
)


def _mechanical_surface_status(findings: list[dict[str, Any]]) -> str:
    for item in findings:
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "undeclared_surface" or item.get("member"):
            return "hit"
    return "clear"


def _mechanical_api_paths(findings: list[dict[str, Any]]) -> set[str]:
    raw: set[str] = set()
    for item in findings:
        if not isinstance(item, dict):
            continue
        if item.get("member"):
            raw.add(str(item["member"]))
        for key in ("members", "api_paths"):
            values = item.get(key) or []
            if isinstance(values, list):
                raw.update(str(value) for value in values if value)
    return _alias_api_paths(raw)


def _normalize_source_citation(
    raw: str,
    *,
    source_paths: set[str],
    source_aliases: dict[str, str],
    source_root: Path | None,
    snapshot: Any | None,
) -> str:
    if raw in source_paths:
        return raw
    if raw in source_aliases:
        return source_aliases[raw]
    if source_root is not None:
        canonical = _canonical_path_for_symbol(source_root, snapshot, raw)
        if canonical in source_paths:
            return canonical
        if snapshot is not None and "." in raw:
            module = raw.rsplit(".", 1)[0]
            path = snapshot.modules.get(module)
            if path is not None:
                try:
                    relative = path.relative_to(source_root).as_posix()
                except ValueError:
                    relative = ""
                if relative in source_paths:
                    return relative
    return raw


def _review_prompt(
    *,
    task_id: str,
    metadata: dict[str, Any],
    hidden: dict[str, str],
    source_evidence: dict[str, str],
    findings: list[dict[str, Any]],
) -> str:
    packet = {
        "task_id": task_id,
        "public_spec": metadata.get("public_spec") or {},
        "evaluation_spec": metadata.get("evaluation_spec") or {},
        "mechanical_findings": findings,
        "hidden_tests": hidden,
        "canonical_source_evidence": source_evidence,
    }
    return (
        "Audit one FeatureLiftBench task. Hidden tests are evaluator evidence, not "
        "a source of requirements. Decide whether each hidden observation is explicit "
        "in the public contract or uniquely recoverable from the canonical source. "
        "Separately decide whether every exercised API member is explicitly declared. "
        "Do not infer facts from filenames alone. Return JSON only with this schema:\n"
        "{\"surface_compliance\":\"pass|fail|undetermined\","
        "\"hidden_fairness\":\"fair|underdetermined|undecided\","
        "\"summary\":\"short evidence-backed summary\",\"findings\":[{"
        "\"rule\":\"surface|fairness\",\"behavior_ids\":[],"
        "\"hidden_nodeids\":[],\"api_paths\":[],\"source_paths\":[],"
        "\"verdict\":\"fair|confirmed_violation|undetermined|scope_preserved|scope_changed|insufficient_evidence\","
        "\"reason\":\"concise, auditable reason\"}]}\n"
        "Every cited id/path must occur in the supplied packet. If evidence is missing, "
        "return undetermined. Do not include chain-of-thought.\n\nPACKET:\n"
        + json.dumps(packet, ensure_ascii=False, sort_keys=True)
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("reviewer response contains no JSON object")
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("reviewer response must be a JSON object")
    return value


def _call_chat(
    config: ReviewerConfig,
    messages: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = {
        "model": config.model,
        "temperature": 0,
        "max_tokens": config.max_output_tokens,
        "reasoning_effort": config.reasoning_effort,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    request = urllib.request.Request(
        config.endpoint,
        data=_canonical_json(payload),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"reviewer API request failed: {exc}") from exc
    choices = raw.get("choices") or []
    if not choices:
        raise ValueError("reviewer API response has no choices")
    choice = choices[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        content = ""
    reasoning = message.get("reasoning_content")
    if not isinstance(reasoning, str):
        reasoning = ""
    usage = raw.get("usage") or {}
    try:
        parsed = _extract_json_object(content)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ReviewerResponseError(
            str(exc),
            usage=usage,
            finish_reason=str(choice.get("finish_reason") or ""),
            content_chars=len(content),
            reasoning_chars=len(reasoning),
        ) from exc
    return parsed, usage


def _call_reviewer(config: ReviewerConfig, prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return _call_chat(
        config,
        [
            {
                "role": "system",
                "content": "You are an evidence-grounded benchmark auditor. Output JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    )


def _merge_usage(total: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    merged = dict(total)
    for key, value in current.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            merged[key] = merged.get(key, 0) + value
    return merged


def _validate_review(
    review: dict[str, Any],
    *,
    metadata: dict[str, Any],
    source_paths: set[str],
    finding_api_paths: set[str] | None = None,
    repair_context: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if review.get("surface_compliance") not in {PASS, FAIL, UNDETERMINED}:
        errors.append("invalid surface_compliance")
    if review.get("hidden_fairness") not in {"fair", "underdetermined", "undecided"}:
        errors.append("invalid hidden_fairness")
    findings = review.get("findings")
    if not isinstance(findings, list):
        return [*errors, "findings must be a list"]
    allowed_behaviors = _behavior_ids(metadata.get("public_spec") or {})
    allowed_nodeids = _mapped_nodeids(metadata)
    allowed_api = _alias_api_paths(_required_api_paths(metadata.get("public_spec") or {}))
    allowed_api |= _alias_api_paths(finding_api_paths or set())
    allowed_rules = {"surface", "fairness"}
    if repair_context is not None:
        allowed_rules.add("repair_scope")
        repair_scope = review.get("repair_scope")
        if repair_scope not in {"scope_preserved", "scope_changed", "insufficient_evidence"}:
            errors.append("invalid repair_scope")
        repair_findings = [
            finding
            for finding in findings
            if isinstance(finding, dict) and finding.get("rule") == "repair_scope"
        ]
        if not repair_findings:
            errors.append("repair review requires a repair_scope finding")
        expected_verdict = {
            "scope_preserved": "scope_preserved",
            "scope_changed": "scope_changed",
            "insufficient_evidence": "insufficient_evidence",
        }.get(repair_scope)
        if expected_verdict and any(
            finding.get("verdict") != expected_verdict for finding in repair_findings
        ):
            errors.append("repair_scope finding verdict does not match repair_scope")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"finding {index} is not an object")
            continue
        if finding.get("rule") not in allowed_rules:
            errors.append(f"finding {index} has invalid rule")
        allowed_verdicts = (
            {"scope_preserved", "scope_changed", "insufficient_evidence"}
            if finding.get("rule") == "repair_scope"
            else {"fair", "confirmed_violation", UNDETERMINED}
        )
        if finding.get("verdict") not in allowed_verdicts:
            errors.append(f"finding {index} has invalid verdict")
        if not isinstance(finding.get("reason"), str) or not finding.get("reason", "").strip():
            errors.append(f"finding {index} has no reason")
        citation_fields = ("behavior_ids", "hidden_nodeids", "api_paths", "source_paths")
        for field in citation_fields:
            if not isinstance(finding.get(field, []), list):
                errors.append(f"finding {index} field {field} is not a list")
        for value in finding.get("behavior_ids") if isinstance(finding.get("behavior_ids"), list) else []:
            if str(value) not in allowed_behaviors:
                errors.append(f"finding {index} cites unknown behavior {value}")
        for value in finding.get("hidden_nodeids") if isinstance(finding.get("hidden_nodeids"), list) else []:
            if str(value) not in allowed_nodeids:
                errors.append(f"finding {index} cites unknown nodeid {value}")
        for value in finding.get("api_paths") if isinstance(finding.get("api_paths"), list) else []:
            if str(value) not in allowed_api:
                errors.append(f"finding {index} cites undeclared API path {value}")
        for value in finding.get("source_paths") if isinstance(finding.get("source_paths"), list) else []:
            if str(value) not in source_paths:
                errors.append(f"finding {index} cites unavailable source path {value}")
    return errors


def _hidden_mapping_index(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in (metadata.get("evaluation_spec") or {}).get("hidden_test_mappings") or []:
        if not isinstance(row, dict) or not row.get("nodeid"):
            continue
        rows.append(
            {
                "nodeid": str(row["nodeid"]),
                "behavior_ids": [str(value) for value in row.get("behavior_ids") or []],
            }
        )
    return rows


def _hidden_nodeid_excerpt(task_dir: Path, nodeid: str, limit: int) -> dict[str, Any]:
    parts = nodeid.split("::")
    relative = Path(parts[0])
    hidden_root = (task_dir / "hidden_tests").resolve()
    path = (task_dir / relative).resolve()
    if not path.is_relative_to(hidden_root) or not path.is_file():
        return {"nodeid": nodeid, "error": "hidden nodeid path is unavailable"}
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"nodeid": nodeid, "error": f"hidden test parse failed: {exc}"}

    target_names = [item.split("[", 1)[0] for item in parts[1:] if item]
    nodes: list[ast.AST] = list(tree.body)
    target: ast.AST | None = None
    for name in target_names:
        target = next(
            (
                node
                for node in nodes
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name
            ),
            None,
        )
        if target is None:
            break
        nodes = list(getattr(target, "body", []))
    if target is None or not hasattr(target, "lineno"):
        return {"nodeid": nodeid, "error": "hidden test function is unavailable"}

    decorators = getattr(target, "decorator_list", [])
    start = min([target.lineno, *[item.lineno for item in decorators]])
    end = int(getattr(target, "end_lineno", target.lineno))
    lines = text.splitlines(keepends=True)
    excerpt = "".join(
        f"{line_number:06d}: {line}"
        for line_number, line in enumerate(lines[start - 1 : end], start=start)
    )
    return {
        "nodeid": nodeid,
        "path": relative.as_posix(),
        "lines": [start, end],
        "excerpt": excerpt[:limit],
        "excerpt_sha256": _sha256_bytes(excerpt[:limit].encode("utf-8")),
    }


def _agent_initial_prompt(
    *,
    task_id: str,
    metadata: dict[str, Any],
    findings: list[dict[str, Any]],
    config: ReviewerConfig,
    repair_context: dict[str, Any] | None = None,
) -> str:
    packet = {
        "task_id": task_id,
        "public_spec": metadata.get("public_spec") or {},
        "hidden_mapping_index": _hidden_mapping_index(metadata),
        "source_entrypoints": _entrypoints(metadata),
        "mechanical_findings": findings,
        "mechanical_surface_status": _mechanical_surface_status(findings),
        "citable_mechanical_api": sorted(_mechanical_api_paths(findings)),
        "source_role": CANONICAL_SOURCE_ROLE,
    }
    if repair_context is not None:
        packet["repair_context"] = repair_context
    repair_schema = (
        '"repair_scope":"scope_preserved|scope_changed|insufficient_evidence",'
        if repair_context is not None
        else ""
    )
    repair_rule = "|repair_scope" if repair_context is not None else ""
    repair_instruction = (
        "For repair_scope, compare pre_repair_public_spec, the repair delta, "
        "the inspected Hidden observations and canonical source. scope_preserved "
        "means the patch only disclosed, corrected or diversified an obligation "
        "already inside the old functional scope; scope_changed means it expanded "
        "or narrowed that scope. A repair_scope finding must repeat the same "
        "verdict value (scope_preserved, scope_changed or insufficient_evidence). "
        "Include one repair_scope finding with citations. "
        if repair_context is not None
        else ""
    )
    return (
        "Audit one FeatureLiftBench task using only the constrained actions below. "
        "Your job is to flag package defects, not to fix them. Hidden tests are "
        "observations, never new requirements. Inspect evidence before submitting. "
        "Do not ask for a shell, arbitrary files, or the whole repository. "
        "Output exactly one JSON object per turn and no prose. Allowed actions:\n"
        f"1. {{\"action\":\"inspect_hidden\",\"nodeids\":[\"an allowed nodeid\"]}} "
        f"(at most {config.agent_max_nodeids_per_turn} nodeids per turn)\n"
        f"2. {{\"action\":\"inspect_source\",\"symbols\":[\"an allowed source_entrypoint\"]}} "
        f"(at most {config.agent_max_symbols_per_turn} symbols per turn)\n"
        "3. {\"action\":\"submit\",\"review\":{"
        "\"surface_compliance\":\"pass|fail|undetermined\","
        "\"hidden_fairness\":\"fair|underdetermined|undecided\","
        "\"summary\":\"short evidence-backed summary\"," + repair_schema + "\"findings\":[{"
        "\"rule\":\"surface|fairness" + repair_rule + "\",\"behavior_ids\":[],"
        "\"hidden_nodeids\":[],\"api_paths\":[],\"source_paths\":[],"
        "\"verdict\":\"fair|confirmed_violation|undetermined\","
        "\"reason\":\"concise auditable reason\"}]}}\n"
        "surface_compliance and hidden_fairness are orthogonal. Hidden may be "
        "semantically fair while required_api omits exercised members; then "
        "surface_compliance=fail and hidden_fairness=fair. Do not treat Python "
        "dunder protocol as an implicit declaration. If mechanical findings list "
        "undeclared members, cite those members to flag a surface defect. "
        "inspect_source returns the canonical pinned upstream; that is the "
        "implementation under review. Do not wait for a separate featurelifted/ "
        "tree, and do not mark surface_compliance undetermined for its absence. "
        "If mechanical_surface_status is hit, set surface_compliance=fail and cite "
        "those members. If it is clear and you inspected hidden tests, set "
        "surface_compliance=pass unless you flag a specific additional undeclared "
        "member. featurelifted.* is the extraction-package alias the coding agent "
        "must implement; canonical source keeps upstream names (graphene, aiohttp, "
        "...). That rename is not a defect. Hidden tests that forbid importing the "
        "upstream package apply to the agent submission, not to canonical source. "
        "A conclusive fair+pass review must inspect every mapped hidden nodeid and "
        "at least one declared source entrypoint. A surface-fail flag only needs "
        "the cited nodeids. Submit at least one finding with citations. Every "
        "citation must have appeared in the initial packet or a tool result. "
        "In source_paths, copy exact file-path keys from source_evidence when "
        "possible; symbols are normalized to those files. " + repair_instruction + "If evidence is "
        "insufficient, submit undetermined. Do not reveal chain-of-thought.\n\n"
        "INITIAL_PACKET:\n" + json.dumps(packet, ensure_ascii=False, sort_keys=True)
    )


def _agent_check_result(
    *,
    status: str,
    reason: str,
    config: ReviewerConfig,
    usage: dict[str, Any],
    trace: list[dict[str, Any]],
    evidence: list[Any] | None = None,
    adjudication: str = "not_needed",
    mechanical_result: str = "error",
    review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "mode": "constrained_agent",
        "model": config.model,
        "prompt_version": AGENT_PROMPT_VERSION,
        "turns": len(trace),
        "usage": usage,
        "trace": trace,
    }
    if review is not None:
        details["review"] = review
    return _check(
        status,
        blocking=False,
        evidence=evidence or [],
        reason=reason,
        mechanical_result=mechanical_result,
        adjudication=adjudication,
        details=details,
    )


def _agent_review_check(
    *,
    task_dir: Path,
    metadata: dict[str, Any],
    source_root: Path | None,
    snapshot: Any | None,
    findings: list[dict[str, Any]],
    config: ReviewerConfig,
    repair_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if source_root is None:
        return _agent_check_result(
            status=UNDETERMINED,
            reason="validator agent requires canonical source materialization",
            config=config,
            usage={},
            trace=[],
        ), []

    mappings = _hidden_mapping_index(metadata)
    allowed_nodeids = {row["nodeid"] for row in mappings}
    allowed_symbols = set(_entrypoints(metadata))
    if not allowed_nodeids or not allowed_symbols:
        return _agent_check_result(
            status=UNDETERMINED,
            reason="validator agent requires mapped hidden nodeids and declared source entrypoints",
            config=config,
            usage={},
            trace=[],
        ), []

    initial = _agent_initial_prompt(
        task_id=task_dir.name,
        metadata=metadata,
        findings=findings,
        config=config,
        repair_context=repair_context,
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a constrained evidence auditor. Follow the JSON action protocol "
                "exactly. Never invent citations."
            ),
        },
        {"role": "user", "content": initial},
    ]
    initial_sha = _sha256_bytes(initial.encode("utf-8"))
    trace: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}
    inspected_nodeids: set[str] = set()
    inspected_symbols: set[str] = set()
    source_paths: set[str] = set()
    source_aliases: dict[str, str] = {}
    seen_actions: set[str] = set()
    recovery_used = False
    submit_repair_used = False
    action_repair_used = False
    call_config = config
    mechanical_api = _mechanical_api_paths(findings)
    max_turns = config.agent_max_turns
    turn = 0

    while turn < max_turns:
        turn += 1
        context_chars = sum(len(message["content"]) for message in messages)
        if context_chars > config.agent_max_context_chars:
            return _agent_check_result(
                status=UNDETERMINED,
                reason="validator agent context budget exhausted",
                config=config,
                usage=usage,
                trace=trace,
                evidence=[{"initial_prompt_sha256": initial_sha, "context_chars": context_chars}],
            ), []
        try:
            action, turn_usage = _call_chat(call_config, messages)
        except ReviewerResponseError as exc:
            usage = _merge_usage(usage, exc.usage)
            trace.append(
                {
                    "turn": turn,
                    "action": "invalid_response",
                    "finish_reason": exc.finish_reason,
                    "content_chars": exc.content_chars,
                    "reasoning_chars": exc.reasoning_chars,
                    "usage": exc.usage,
                }
            )
            if recovery_used or int(usage.get("total_tokens", 0)) > config.agent_max_total_tokens:
                return _agent_check_result(
                    status=UNDETERMINED,
                    reason="validator agent returned repeated invalid JSON",
                    config=config,
                    usage=usage,
                    trace=trace,
                    evidence=[str(exc), {"initial_prompt_sha256": initial_sha}],
                ), []
            recovery_used = True
            call_config = replace(
                config,
                max_output_tokens=min(max(config.max_output_tokens * 2, 8_192), 16_384),
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "RECOVERY: the previous response did not contain a valid JSON action. "
                        "Return exactly one protocol JSON object now, without analysis or prose. "
                        "Use submit if the inspected evidence is sufficient."
                    ),
                }
            )
            continue
        except (RuntimeError, ValueError, OSError) as exc:
            return _agent_check_result(
                status=UNDETERMINED,
                reason="validator agent failed closed",
                config=config,
                usage=usage,
                trace=trace,
                evidence=[str(exc), {"initial_prompt_sha256": initial_sha}],
            ), []
        usage = _merge_usage(usage, turn_usage)
        if int(usage.get("total_tokens", 0)) > config.agent_max_total_tokens:
            return _agent_check_result(
                status=UNDETERMINED,
                reason="validator agent token budget exhausted",
                config=config,
                usage=usage,
                trace=trace,
                evidence=[{"initial_prompt_sha256": initial_sha}],
            ), []

        action_name = str(action.get("action") or "")
        action_key = _sha256_json(action)
        if action_key in seen_actions:
            return _agent_check_result(
                status=UNDETERMINED,
                reason="validator agent repeated an identical action",
                config=config,
                usage=usage,
                trace=trace,
                evidence=[{"action": action_name, "turn": turn}],
            ), []
        seen_actions.add(action_key)

        if action_name == "inspect_hidden":
            requested = action.get("nodeids")
            if (
                not isinstance(requested, list)
                or not requested
                or len(requested) > config.agent_max_nodeids_per_turn
                or any(str(value) not in allowed_nodeids for value in requested)
            ):
                trace.append({
                    "turn": turn,
                    "action": "inspect_hidden",
                    "requested": requested,
                    "rejected": ["request must use only allowed hidden nodeids within the per-turn limit"],
                    "usage": turn_usage,
                })
                if action_repair_used:
                    return _agent_check_result(
                        status=UNDETERMINED,
                        reason="validator agent repeatedly requested invalid hidden evidence",
                        config=config,
                        usage=usage,
                        trace=trace,
                        evidence=[{"turn": turn, "requested": requested}],
                    ), []
                action_repair_used = True
                if turn >= max_turns:
                    max_turns += 1
                messages.extend([
                    {"role": "assistant", "content": json.dumps(action, ensure_ascii=False)},
                    {"role": "user", "content": "ACTION_REJECTED: request only allowed_nodeids from the initial packet. Allowed nodeids: " + json.dumps(sorted(allowed_nodeids), ensure_ascii=False) + ". Continue with one valid JSON action."},
                ])
                continue
            nodeids = [str(value) for value in requested]
            per_item = max(1_000, config.agent_tool_result_chars // len(nodeids))
            observation = {
                "tool": "inspect_hidden",
                "results": [
                    _hidden_nodeid_excerpt(task_dir, nodeid, per_item)
                    for nodeid in nodeids
                ],
            }
            inspected_nodeids.update(nodeids)
        elif action_name == "inspect_source":
            requested = action.get("symbols")
            if (
                not isinstance(requested, list)
                or not requested
                or len(requested) > config.agent_max_symbols_per_turn
                or any(str(value) not in allowed_symbols for value in requested)
            ):
                trace.append({
                    "turn": turn,
                    "action": "inspect_source",
                    "requested": requested,
                    "rejected": ["request must use only declared source_entrypoints within the per-turn limit"],
                    "usage": turn_usage,
                })
                if action_repair_used:
                    return _agent_check_result(
                        status=UNDETERMINED,
                        reason="validator agent repeatedly requested invalid source evidence",
                        config=config,
                        usage=usage,
                        trace=trace,
                        evidence=[{"turn": turn, "requested": requested}],
                    ), []
                action_repair_used = True
                if turn >= max_turns:
                    max_turns += 1
                messages.extend([
                    {"role": "assistant", "content": json.dumps(action, ensure_ascii=False)},
                    {"role": "user", "content": "ACTION_REJECTED: request only source_entrypoints from the initial packet. Allowed source_entrypoints: " + json.dumps(sorted(allowed_symbols), ensure_ascii=False) + ". Continue with one valid JSON action."},
                ])
                continue
            symbols = [str(value) for value in requested]
            source, unavailable = _source_evidence(
                source_root,
                snapshot,
                symbols,
                config.agent_tool_result_chars,
            )
            observation = {
                "tool": "inspect_source",
                "source_role": CANONICAL_SOURCE_ROLE,
                "symbols": symbols,
                "source_evidence": source,
                "allowed_source_paths": sorted(source),
                "citation_rule": (
                    "source_paths must use exact allowed_source_paths values; "
                    "these files are the canonical implementation"
                ),
                "unavailable": unavailable,
            }
            inspected_symbols.update(symbols)
            source_paths.update(source)
            for symbol in symbols:
                canonical = _canonical_path_for_symbol(source_root, snapshot, symbol)
                if canonical in source:
                    source_aliases[symbol] = canonical
        elif action_name == "submit":
            submitted_review = action.get("review")
            review = (
                json.loads(json.dumps(submitted_review))
                if isinstance(submitted_review, dict)
                else submitted_review
            )
            citation_normalizations: list[dict[str, str]] = []
            if isinstance(review, dict):
                for finding in review.get("findings") or []:
                    if not isinstance(finding, dict):
                        continue
                    normalized_paths = []
                    for value in finding.get("source_paths") or []:
                        raw_path = str(value)
                        normalized = _normalize_source_citation(
                            raw_path,
                            source_paths=source_paths,
                            source_aliases=source_aliases,
                            source_root=source_root,
                            snapshot=snapshot,
                        )
                        normalized_paths.append(normalized)
                        if normalized != raw_path:
                            citation_normalizations.append(
                                {"submitted": raw_path, "canonical_path": normalized}
                            )
                    finding["source_paths"] = normalized_paths
            if not isinstance(review, dict):
                errors = ["submit action has no review object"]
            else:
                errors = _validate_review(
                    review,
                    metadata=metadata,
                    source_paths=source_paths,
                    finding_api_paths=mechanical_api,
                    repair_context=repair_context,
                )
                if not review.get("findings"):
                    errors.append("agent review must contain at least one cited finding")
                cited_nodeids = {
                    str(value)
                    for finding in review.get("findings") or []
                    if isinstance(finding, dict)
                    for value in finding.get("hidden_nodeids") or []
                }
                if not cited_nodeids.issubset(inspected_nodeids):
                    errors.append("agent cited hidden nodeids it did not inspect")
                fair_claim = review.get("hidden_fairness") == "fair"
                pass_claim = review.get("surface_compliance") == PASS
                if fair_claim and pass_claim and inspected_nodeids != allowed_nodeids:
                    errors.append("fair+pass review did not inspect every mapped hidden nodeid")
                if (fair_claim or pass_claim) and not inspected_symbols:
                    errors.append("positive review did not inspect canonical source")
                mechanical_surface = _mechanical_surface_status(findings)
                surface = review.get("surface_compliance")
                if mechanical_surface == "hit" and surface == PASS:
                    errors.append(
                        "mechanical undeclared members exist; surface_compliance cannot be pass"
                    )
                if mechanical_surface == "hit" and surface == UNDETERMINED:
                    errors.append(
                        "mechanical undeclared members exist; set surface_compliance=fail and cite them"
                    )
                if (
                    mechanical_surface == "clear"
                    and surface == UNDETERMINED
                    and inspected_nodeids
                ):
                    errors.append(
                        "mechanical C1 is clear and hidden tests were inspected; "
                        "set surface_compliance=pass. Canonical source is the implementation; "
                        "do not wait for a separate featurelifted tree"
                    )
                if mechanical_surface == "clear" and surface == FAIL:
                    cited: set[str] = set()
                    for finding in review.get("findings") or []:
                        if not isinstance(finding, dict):
                            continue
                        if finding.get("verdict") != "confirmed_violation":
                            continue
                        for value in finding.get("api_paths") or []:
                            cited.add(str(value))
                    cited_aliases = _alias_api_paths(cited)
                    declared = _alias_api_paths(
                        _required_api_paths(metadata.get("public_spec") or {})
                    )
                    if not (cited_aliases - declared):
                        errors.append(
                            "surface_compliance=fail requires an undeclared exercised member. "
                            "featurelifted.* is the extraction alias of canonical source; "
                            "upstream names and upstream imports in canonical source are expected. "
                            "Forbidden-import tests apply to the agent submission, not canonical source"
                        )
            trace.append(
                {
                    "turn": turn,
                    "action": "submit",
                    "request_sha256": action_key,
                    "citation_normalizations": citation_normalizations,
                    "rejected": errors,
                    "usage": turn_usage,
                }
            )
            if errors:
                if submit_repair_used:
                    return _agent_check_result(
                        status=UNDETERMINED,
                        reason="validator agent submission failed deterministic verification",
                        config=config,
                        usage=usage,
                        trace=trace,
                        evidence=[*errors, {"initial_prompt_sha256": initial_sha}],
                        review=review if isinstance(review, dict) else None,
                    ), []
                submit_repair_used = True
                if turn >= max_turns:
                    max_turns += 1
                messages.extend(
                    [
                        {
                            "role": "assistant",
                            "content": json.dumps(action, ensure_ascii=False),
                        },
                        {
                            "role": "user",
                            "content": (
                                "SUBMIT_REJECTED: deterministic verification failed. "
                                "Resubmit exactly one submit action and fix the listed validation errors. "
                                "Use allowed_source_paths file paths, not symbols. "
                                "Undeclared mechanical members may be cited with or without "
                                "the featurelifted. prefix. Canonical source is the "
                                "implementation under its upstream names; featurelifted.* "
                                "is only the extraction alias. Forbidden-import tests do "
                                "not apply to canonical source.\n"
                                + json.dumps(
                                    {
                                        "errors": errors,
                                        "allowed_source_paths": sorted(source_paths),
                                        "citable_mechanical_api": sorted(mechanical_api),
                                    },
                                    ensure_ascii=False,
                                )
                            ),
                        },
                    ]
                )
                continue

            assert isinstance(review, dict)
            semantic_findings = []
            for item in review.get("findings") or []:
                finding = dict(item)
                semantic_rule = finding.pop("rule", "")
                semantic_findings.append(
                    {
                        "task_id": task_dir.name,
                        "rule": "L2_AGENT_REVIEW",
                        "kind": f"agent_{semantic_rule}",
                        "semantic_rule": semantic_rule,
                        **finding,
                    }
                )
            conclusive = (
                review.get("surface_compliance") == PASS
                and review.get("hidden_fairness") == "fair"
                and (
                    repair_context is None
                    or review.get("repair_scope") == "scope_preserved"
                )
            )
            flagged = any(
                item.get("verdict") in {"confirmed_violation", "scope_changed"}
                for item in review.get("findings") or []
                if isinstance(item, dict)
            )
            return _agent_check_result(
                status=PASS if conclusive else UNDETERMINED,
                reason=(
                    "validator agent returned a citation-valid fair review"
                    if conclusive
                    else "validator agent flagged package defects"
                    if flagged
                    else "validator agent raised semantic findings requiring adjudication"
                ),
                config=config,
                usage=usage,
                trace=trace,
                evidence=[review],
                adjudication="not_needed" if conclusive else "pending",
                mechanical_result="clear" if conclusive else "hit",
                review=review,
            ), semantic_findings
        else:
            return _agent_check_result(
                status=UNDETERMINED,
                reason="validator agent returned an unknown action",
                config=config,
                usage=usage,
                trace=trace,
                evidence=[{"turn": turn, "action": action_name}],
            ), []

        observation_text = json.dumps(observation, ensure_ascii=False, sort_keys=True)
        observation_sha = _sha256_bytes(observation_text.encode("utf-8"))
        trace.append(
            {
                "turn": turn,
                "action": action_name,
                "requested": action.get("nodeids") or action.get("symbols") or [],
                "observation_keys": sorted(
                    source_paths if action_name == "inspect_source" else inspected_nodeids
                ),
                "observation_sha256": observation_sha,
                "usage": turn_usage,
            }
        )
        messages.extend(
            [
                {"role": "assistant", "content": json.dumps(action, ensure_ascii=False)},
                {"role": "user", "content": "TOOL_RESULT:\n" + observation_text},
            ]
        )

    return _agent_check_result(
        status=UNDETERMINED,
        reason="validator agent exhausted its turn budget without submitting",
        config=config,
        usage=usage,
        trace=trace,
        evidence=[{"initial_prompt_sha256": initial_sha}],
    ), []


def _api_review_check(
    *,
    task_dir: Path,
    metadata: dict[str, Any],
    source_root: Path | None,
    snapshot: Any | None,
    findings: list[dict[str, Any]],
    config: ReviewerConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if source_root is None:
        return _check(
            UNDETERMINED,
            blocking=False,
            reason="API review requires canonical source materialization",
            mechanical_result="error",
        ), []
    hidden, hidden_truncated = _hidden_payload(task_dir, config.max_hidden_chars)
    source, source_truncated = _source_evidence(
        source_root,
        snapshot,
        _entrypoints(metadata),
        config.max_source_chars,
    )
    if hidden_truncated or source_truncated:
        return _check(
            UNDETERMINED,
            blocking=False,
            evidence=[
                {"hidden_truncated": hidden_truncated, "source_truncated": source_truncated}
            ],
            reason="API evidence packet exceeded configured limits",
            mechanical_result="error",
        ), []
    prompt = _review_prompt(
        task_id=task_dir.name,
        metadata=metadata,
        hidden=hidden,
        source_evidence=source,
        findings=findings,
    )
    prompt_sha = _sha256_bytes(prompt.encode("utf-8"))
    try:
        review, usage = _call_reviewer(config, prompt)
        errors = _validate_review(
            review,
            metadata=metadata,
            source_paths=set(source),
            finding_api_paths={
                str(item.get("member"))
                for item in findings
                if item.get("member")
            },
        )
    except (RuntimeError, ValueError, OSError) as exc:
        return _check(
            UNDETERMINED,
            blocking=False,
            evidence=[str(exc), {"prompt_sha256": prompt_sha}],
            reason="API reviewer failed closed",
            mechanical_result="error",
        ), []
    if errors:
        return _check(
            UNDETERMINED,
            blocking=False,
            evidence=[*errors, {"prompt_sha256": prompt_sha}],
            reason="API reviewer cited evidence outside the supplied packet",
            mechanical_result="error",
        ), []
    review_findings = []
    for item in review.get("findings") or []:
        finding = dict(item)
        semantic_rule = finding.pop("rule", "")
        review_findings.append(
            {
                "task_id": task_dir.name,
                "rule": "L2_API_REVIEW",
                "kind": f"api_{semantic_rule}" if semantic_rule else "api_semantic",
                "semantic_rule": semantic_rule,
                **finding,
            }
        )
    conclusive = (
        review.get("surface_compliance") == PASS
        and review.get("hidden_fairness") == "fair"
    )
    return _check(
        PASS if conclusive else UNDETERMINED,
        blocking=False,
        evidence=[review],
        reason=(
            "API reviewer returned a citation-valid fair review"
            if conclusive
            else "API reviewer raised semantic findings requiring adjudication"
        ),
        mechanical_result="clear" if conclusive else "hit",
        adjudication="not_needed" if conclusive else "pending",
        details={
            "model": config.model,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": prompt_sha,
            "usage": usage,
        },
    ), review_findings


def _task_record(
    *,
    task_dir: Path,
    source_workspace: CanonicalSourceWorkspace,
    oracle_runs: dict[str, list[dict[str, Any]]],
    upstream_direct: dict[str, dict[str, Any]],
    adjudications: dict[tuple[str, str], dict[str, str]],
    reviewer: ReviewerConfig | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    task_id = task_dir.name
    findings: list[dict[str, Any]] = []
    metadata_path = task_dir / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        checks = {
            "L1_PACKAGE": _check(
                FAIL,
                blocking=True,
                evidence=[str(exc)],
                reason="metadata.json is unreadable",
                mechanical_result="hit",
                adjudication="confirmed_violation",
            )
        }
        return {
            "task_id": task_id,
            "gate_version": GATE_VERSION,
            "label": aggregate_label(checks),
            "input_identity": {},
            "checks": checks,
        }, findings

    identity, source_root, source_error = source_workspace.identity(task_id)
    validation = validate_task(task_dir)
    checks: dict[str, dict[str, Any]] = {
        "L1_PACKAGE": _check(
            PASS if validation.valid else FAIL,
            blocking=True,
            evidence=validation.errors,
            reason="task package validation passed" if validation.valid else "task package validation failed",
            mechanical_result="clear" if validation.valid else "hit",
            adjudication="not_needed" if validation.valid else "confirmed_violation",
            details={"warnings": validation.warnings},
        ),
        "SOURCE_IDENTITY": _source_check(
            identity, source_error, source_root is not None
        ),
    }
    surface, surface_findings = _surface_check(task_dir, metadata.get("public_spec") or {}, adjudications)
    checks["L2_C1_SURFACE"] = surface
    findings.extend(surface_findings)
    entrypoint, entry_findings, snapshot = _entrypoint_check(
        task_id, metadata, source_root, adjudications
    )
    checks["L2_C2_ENTRYPOINT"] = entrypoint
    findings.extend(entry_findings)
    checks["L3_ORACLE_N3"] = _oracle_check(
        task_id,
        oracle_runs.get(task_id, []),
        str(identity.get("source_tree_sha256") or ""),
    )
    checks["L3_G2PRIME_UPSTREAM"] = _upstream_direct_check(
        task_id, upstream_direct.get(task_id)
    )
    checks["L4_ISOLATION_N3"] = _isolation_check(oracle_runs.get(task_id, []))
    checks["L5_TASK_LEAKAGE"] = _leakage_check(task_dir)
    checks["L5_C4_TEST_OVERLAP"] = _overlap_check(task_dir)
    if reviewer is not None:
        if reviewer.mode == "agent":
            semantic_pending = any(
                checks[name].get("status") == UNDETERMINED
                for name in ("L2_C1_SURFACE", "L2_C2_ENTRYPOINT")
            )
            if reviewer.agent_pending_only and not semantic_pending:
                checks["L2_AGENT_REVIEW"] = _check(
                    PASS,
                    blocking=False,
                    reason="validator agent skipped a mechanically clear task",
                    mechanical_result="clear",
                    details={
                        "mode": "constrained_agent",
                        "prompt_version": AGENT_PROMPT_VERSION,
                        "skipped": True,
                    },
                )
            else:
                agent_check, agent_findings = _agent_review_check(
                    task_dir=task_dir,
                    metadata=metadata,
                    source_root=source_root,
                    snapshot=snapshot,
                    findings=findings,
                    config=reviewer,
                )
                checks["L2_AGENT_REVIEW"] = agent_check
                findings.extend(agent_findings)
        else:
            api_check, api_findings = _api_review_check(
                task_dir=task_dir,
                metadata=metadata,
                source_root=source_root,
                snapshot=snapshot,
                findings=findings,
                config=reviewer,
            )
            checks["L2_API_REVIEW"] = api_check
            findings.extend(api_findings)

    input_identity = {
        "task_revision": metadata.get("task_revision"),
        "spec_hash": metadata.get("spec_hash"),
        "generated_task_hash": metadata.get("generated_task_hash"),
        "task_input_sha256": _sha256_tree(task_dir, excluded_top={"repo"}),
        "source_tree_sha256": identity.get("source_tree_sha256"),
        "source_snapshot_id": identity.get("source_snapshot_id"),
    }
    return {
        "task_id": task_id,
        "gate_version": GATE_VERSION,
        "label": aggregate_label(checks),
        "input_identity": input_identity,
        "checks": checks,
        "blocking_failures": [
            name for name, row in checks.items()
            if row.get("blocking") and row.get("status") == FAIL
        ],
        "pending_rules": [
            name for name, row in checks.items()
            if row.get("blocking") and row.get("status") == UNDETERMINED
        ],
    }, findings


def _task_ids_for_suite(tasks_root: Path, task_file: str, requested: tuple[str, ...]) -> list[str]:
    if task_file:
        path = REPO_ROOT / task_file
        ids = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    else:
        ids = sorted(path.name for path in tasks_root.iterdir() if path.is_dir())
    if requested:
        unknown = sorted(set(requested) - set(ids))
        if unknown:
            raise ValueError(f"task ids are not in suite: {unknown}")
        ids = [task_id for task_id in ids if task_id in set(requested)]
    return ids


def _default_output(benchmark: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return REPO_ROOT / "reports" / "benchmark_gate" / f"{benchmark}_{stamp}"


def _render_report(payload: dict[str, Any]) -> str:
    rows = payload["tasks"]
    labels = Counter(row["label"] for row in rows)
    checks: Counter[tuple[str, str]] = Counter()
    for row in rows:
        for name, result in row["checks"].items():
            checks[(name, result["status"])] += 1
    out = ["# FeatureLiftBench Benchmark Gate", ""]
    out.append(f"- Gate: `{payload['gate_version']}`")
    out.append(f"- Benchmark: `{payload['benchmark']}`")
    out.append(f"- Tasks: {len(rows)}")
    out.append(
        "- Labels: "
        + ", ".join(f"`{key}`={labels.get(key, 0)}" for key in (MEETS, VIOLATES, UNDETERMINED))
    )
    out.append("")
    out.extend(["## Checks", "", "| Check | pass | fail | undetermined |", "| --- | ---: | ---: | ---: |"])
    for name in sorted({key[0] for key in checks}):
        out.append(
            f"| `{name}` | {checks[(name, PASS)]} | {checks[(name, FAIL)]} | "
            f"{checks[(name, UNDETERMINED)]} |"
        )
    out.extend(["", "## Pending or failing tasks", "", "| Task | Label | Confirmed failures | Pending |", "| --- | --- | --- | --- |"])
    for row in rows:
        if row["label"] == MEETS:
            continue
        failures = ", ".join(row.get("blocking_failures") or []) or "-"
        pending = ", ".join(row.get("pending_rules") or []) or "-"
        out.append(f"| `{row['task_id']}` | `{row['label']}` | {failures} | {pending} |")
    out.append("")
    return "\n".join(out)


def _write_outputs(
    output: Path,
    payload: dict[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    output.mkdir(parents=True, exist_ok=False)
    tasks_dir = output / "tasks"
    tasks_dir.mkdir()
    for row in payload["tasks"]:
        (tasks_dir / f"{row['task_id']}.json").write_text(
            json.dumps(row, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    manifest = {key: value for key, value in payload.items() if key != "tasks"}
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "gate_report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "gate_report.md").write_text(_render_report(payload), encoding="utf-8")
    with (output / "findings.jsonl").open("w", encoding="utf-8") as handle:
        for row in findings:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    queue_rows = [
        row for row in findings
        if any(
            task["task_id"] == row["task_id"]
            and (task["checks"].get(row["rule"]) or {}).get("adjudication") == "pending"
            for task in payload["tasks"]
        )
    ]
    queue_fields = ["task_id", "rule", "kind", "member", "symbol", "hidden_files", "verdict", "rationale", "provenance"]
    with (output / "adjudication_queue.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=queue_fields, extrasaction="ignore")
        writer.writeheader()
        for row in queue_rows:
            normalized = dict(row)
            if isinstance(normalized.get("hidden_files"), list):
                normalized["hidden_files"] = ";".join(normalized["hidden_files"])
            writer.writerow(normalized)

    flag_fields = [
        "task_id",
        "semantic_rule",
        "verdict",
        "behavior_ids",
        "hidden_nodeids",
        "api_paths",
        "source_paths",
        "reason",
    ]
    flags = [
        row
        for row in findings
        if row.get("rule") == "L2_AGENT_REVIEW"
        and row.get("verdict") == "confirmed_violation"
    ]
    with (output / "agent_unqualified.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=flag_fields, extrasaction="ignore")
        writer.writeheader()
        for row in flags:
            normalized = dict(row)
            for key in ("behavior_ids", "hidden_nodeids", "api_paths", "source_paths"):
                if isinstance(normalized.get(key), list):
                    normalized[key] = ";".join(str(value) for value in normalized[key])
            writer.writerow(normalized)

    for label in (MEETS, VIOLATES, UNDETERMINED):
        ids = [row["task_id"] for row in payload["tasks"] if row["label"] == label]
        (output / f"{label}.txt").write_text(
            "\n".join(ids) + ("\n" if ids else ""),
            encoding="utf-8",
        )


def run_benchmark_gate(options: GateRunOptions) -> dict[str, Any]:
    """Run the read-only P0 benchmark gate and write a versioned evidence ledger."""

    if options.reviewer is not None and not options.private_evaluator_policy_acknowledged:
        raise ValueError(
            "--api-review requires explicit acknowledgement that private evaluator "
            "data is sent only to a no-training/no-retention endpoint"
        )
    catalog = load_catalog()
    suite = get_suite(catalog, options.benchmark)
    tasks_root = (REPO_ROOT / suite.tasks_root).resolve()
    registry_path = (REPO_ROOT / suite.source_registry).resolve()
    task_ids = _task_ids_for_suite(tasks_root, suite.task_file, options.task_ids)
    if not task_ids:
        raise ValueError(f"benchmark suite has no tasks: {options.benchmark}")
    missing = [task_id for task_id in task_ids if not (tasks_root / task_id).is_dir()]
    if missing:
        raise ValueError(f"suite tasks are missing from tasks_root: {missing[:10]}")

    adjudications = load_adjudications(options.adjudications)
    oracle_runs, oracle_sha = _load_oracle_evidence(options.oracle_summary)
    upstream_direct, upstream_direct_sha = _load_upstream_direct_evidence(
        options.upstream_direct_summary
    )
    output = options.output or _default_output(options.benchmark)
    source_workspace = CanonicalSourceWorkspace(
        registry_path,
        materialize=options.source_materialization,
    )
    rows: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    try:
        for task_id in task_ids:
            row, task_findings = _task_record(
                task_dir=tasks_root / task_id,
                source_workspace=source_workspace,
                oracle_runs=oracle_runs,
                upstream_direct=upstream_direct,
                adjudications=adjudications,
                reviewer=options.reviewer,
            )
            rows.append(row)
            findings.extend(task_findings)
    finally:
        source_workspace.close()

    label_counts = Counter(row["label"] for row in rows)
    payload: dict[str, Any] = {
        "schema_version": GATE_VERSION,
        "gate_version": GATE_VERSION,
        "prompt_version": (
            AGENT_PROMPT_VERSION
            if options.reviewer and options.reviewer.mode == "agent"
            else PROMPT_VERSION if options.reviewer else None
        ),
        "generated_at": _utc_now(),
        "benchmark": suite.id,
        "suite_status": suite.status,
        "tasks_root": suite.tasks_root,
        "source_registry": suite.source_registry,
        "source_registry_sha256": sha256_file(registry_path),
        "oracle_summary": str(options.oracle_summary) if options.oracle_summary else None,
        "oracle_summary_sha256": oracle_sha or None,
        "upstream_direct_summary": (
            str(options.upstream_direct_summary)
            if options.upstream_direct_summary
            else None
        ),
        "upstream_direct_summary_sha256": upstream_direct_sha or None,
        "adjudications": str(options.adjudications) if options.adjudications else None,
        "adjudications_sha256": (
            sha256_file(options.adjudications) if options.adjudications else None
        ),
        "task_count": len(rows),
        "task_set_sha256": _sha256_bytes(("\n".join(task_ids) + "\n").encode("utf-8")),
        "label_counts": {
            MEETS: label_counts.get(MEETS, 0),
            VIOLATES: label_counts.get(VIOLATES, 0),
            UNDETERMINED: label_counts.get(UNDETERMINED, 0),
        },
        "api_reviewer": (
            {
                "enabled": True,
                "mode": options.reviewer.mode,
                "model": options.reviewer.model,
                "endpoint": options.reviewer.public_endpoint_id,
                "private_evaluator_policy_acknowledged": True,
            }
            if options.reviewer
            else {"enabled": False}
        ),
        "publication": {
            "selection_written": False,
            "reason": "P0 gate runs are report-only; publication is an explicit P1 action",
        },
        "tasks": rows,
    }
    _write_outputs(output, payload, findings)
    payload["output"] = str(output)
    return payload


def reviewer_config_from_environment(
    *,
    model: str | None,
    api_base: str | None,
    api_key_env: str,
    timeout_seconds: int,
    env_values: dict[str, str] | None = None,
    mode: str = "one_shot",
    max_output_tokens: int = 4_096,
    reasoning_effort: str = "low",
    agent_max_turns: int = 6,
    agent_max_total_tokens: int = 40_000,
    agent_pending_only: bool = True,
) -> ReviewerConfig:
    file_values = env_values or {}

    def value(name: str) -> str:
        return os.environ.get(name, "").strip() or str(file_values.get(name, "")).strip()

    resolved_model = (
        model
        or value("FEATURELIFTBENCH_VALIDATOR_MODEL")
        or value("FEATURELIFTBENCH_MODEL")
    )
    resolved_base = (
        api_base
        or value("FEATURELIFTBENCH_VALIDATOR_API_BASE")
        or value("FEATURELIFTBENCH_API_BASE")
    )
    resolved_key = value(api_key_env)
    if not resolved_key and api_key_env != "FEATURELIFTBENCH_API_KEY":
        resolved_key = value("FEATURELIFTBENCH_API_KEY")
    missing = [
        name
        for name, value in (
            ("review model", resolved_model),
            ("API base", resolved_base),
            (f"API key env {api_key_env}", resolved_key),
        )
        if not value
    ]
    if missing:
        raise ValueError("missing API reviewer configuration: " + ", ".join(missing))
    if mode not in {"one_shot", "agent"}:
        raise ValueError(f"unknown reviewer mode: {mode}")
    if reasoning_effort not in {"low", "high", "max"}:
        raise ValueError(f"unknown reviewer reasoning effort: {reasoning_effort}")
    if min(max_output_tokens, agent_max_turns, agent_max_total_tokens) <= 0:
        raise ValueError("reviewer token and turn budgets must be positive")
    return ReviewerConfig(
        model=resolved_model,
        api_base=resolved_base,
        api_key=resolved_key,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
        mode=mode,
        agent_max_turns=agent_max_turns,
        agent_max_total_tokens=agent_max_total_tokens,
        agent_pending_only=agent_pending_only,
    )
