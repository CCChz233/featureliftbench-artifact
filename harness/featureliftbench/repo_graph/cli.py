"""Offline CLI for building and querying Repository Semantic Graph snapshots."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from .builder import GraphBuilder
from .hashing import digest_json
from .protocol import dumps_response, response_payload
from .query import GraphQueryEngine
from .policy import INSPECT_MAX_CHARS_ENV, QUERY_MAX_CHARS_ENV, ROOT_ENV
from .ledger import RepoGraphLedger
from .storage import JsonlGraphStore
from .submission import compare_submission, sync_submission
from .runtime import task_closure_result
from .support import build_operational_support


DEFAULT_QUERY_BUDGET = 12_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flb-rsg")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="build a deterministic graph snapshot")
    build_parser.add_argument("--repo", type=Path, required=True)
    build_parser.add_argument("--output", type=Path, required=True)
    build_parser.add_argument("--language", action="append", choices=["python", "go"])

    for command in (
        "task-closure",
        "bootstrap",
        "search",
        "inspect",
        "support",
        "paths",
        "closure",
        "risks",
        "self-check",
    ):
        query_parser = subparsers.add_parser(command)
        query_parser.add_argument("--graph", type=Path)
        query_parser.add_argument(
            "--max-chars",
            type=int,
            default=None,
        )
        if command == "bootstrap":
            query_parser.add_argument("--max-nodes", type=int, default=30)
        elif command == "search":
            query_parser.add_argument("query")
            query_parser.add_argument("--kind", action="append")
            query_parser.add_argument("--limit", type=int, default=20)
            query_parser.add_argument("--offset", type=int, default=0)
        elif command == "inspect":
            query_parser.add_argument("node")
            query_parser.add_argument("--neighbor-limit", type=int, default=30)
        elif command == "support":
            query_parser.add_argument(
                "--seed",
                action="append",
                dest="seeds",
                required=True,
                help="seed stable_id or symbol name (repeatable)",
            )
            query_parser.add_argument(
                "--budget-tokens",
                type=int,
                default=int(os.environ.get("FEATURELIFTBENCH_RSG_BUDGET_TOKENS", "8000") or "8000"),
            )
            query_parser.add_argument("--max-depth", type=int, default=4)
            query_parser.add_argument("--max-nodes", type=int, default=80)
        elif command == "paths":
            query_parser.add_argument("source")
            query_parser.add_argument("target")
            query_parser.add_argument("--max-depth", type=int, default=4)
            query_parser.add_argument("--max-paths", type=int, default=5)
        elif command == "closure":
            query_parser.add_argument("entrypoint", nargs="+")
            query_parser.add_argument("--max-nodes", type=int, default=100)
            query_parser.add_argument("--include-candidates", action="store_true")
        elif command == "risks":
            query_parser.add_argument("node", nargs="*")
            query_parser.add_argument("--limit", type=int, default=20)
            query_parser.add_argument("--offset", type=int, default=0)

    for command in ("submission-check", "sync-submission", "compare"):
        submission_parser = subparsers.add_parser(command)
        submission_parser.add_argument("--root", type=Path)
        submission_parser.add_argument("--submission", type=Path)
        submission_parser.add_argument("--max-chars", type=int, default=None)

    claim_parser = subparsers.add_parser("claim")
    claim_actions = claim_parser.add_subparsers(dest="ledger_action", required=True)
    claim_add = claim_actions.add_parser("add")
    claim_add.add_argument("--subject", required=True)
    claim_add.add_argument("--predicate", required=True)
    claim_add.add_argument("--object", default="")
    claim_add.add_argument("--classification", default="unresolved")
    claim_add.add_argument("--confidence", type=float, default=0.5)
    claim_update = claim_actions.add_parser("update")
    claim_update.add_argument("claim_id")
    claim_update.add_argument("--status", required=True)
    claim_update.add_argument("--evidence", action="append", default=[])
    claim_update.add_argument("--classification")
    claim_actions.add_parser("list")
    claim_parser.add_argument("--root", type=Path)
    claim_parser.add_argument("--max-chars", type=int, default=None)

    evidence_parser = subparsers.add_parser("evidence")
    evidence_actions = evidence_parser.add_subparsers(dest="ledger_action", required=True)
    evidence_record = evidence_actions.add_parser("record")
    evidence_record.add_argument("--kind", required=True)
    evidence_record.add_argument("--probe-type", required=True)
    evidence_record.add_argument("--evidence-class", required=True)
    evidence_record.add_argument("--status", required=True)
    evidence_record.add_argument("--result-summary", required=True)
    evidence_record.add_argument("--input-summary", default="")
    evidence_record.add_argument("--command-text", default="")
    evidence_record.add_argument("--claim", action="append", default=[])
    evidence_record.add_argument("--symbol", action="append", default=[])
    evidence_actions.add_parser("list")
    evidence_parser.add_argument("--root", type=Path)
    evidence_parser.add_argument("--max-chars", type=int, default=None)

    for command in ("freshness", "stopping-check", "detectors"):
        state_parser = subparsers.add_parser(command)
        state_parser.add_argument("--root", type=Path)
        state_parser.add_argument("--max-chars", type=int, default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            return _build(args)
        if args.command in {"submission-check", "sync-submission", "compare"}:
            return _submission_command(args)
        if args.command in {"claim", "evidence", "freshness", "stopping-check", "detectors"}:
            return _ledger_command(args)
        return _query(args)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        _audit_failure(args, exc)
        print(f"flb-rsg: {exc}", file=sys.stderr)
        return 2


def _build(args: argparse.Namespace) -> int:
    repository = args.repo.resolve()
    output_candidate = args.output.resolve()
    if output_candidate == repository or repository in output_candidate.parents:
        raise ValueError("graph output must be outside the source repository")
    snapshot = GraphBuilder().build(args.repo, languages=args.language)
    output = JsonlGraphStore().write(snapshot, args.output)
    print(
        json.dumps(
            {
                "output": str(output),
                "snapshot_id": snapshot.manifest["snapshot_id"],
                "graph_hash": snapshot.manifest["graph_hash"],
                "counts": snapshot.manifest["counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _query(args: argparse.Namespace) -> int:
    if args.graph:
        graph_path = args.graph.resolve()
        graph_root = _configured_graph_root() or (
            graph_path.parent if graph_path.name == "base" else graph_path
        )
    else:
        graph_root = _resolve_graph_root()
        graph_path = graph_root / "base"
    max_chars = _max_chars(args.command, args.max_chars)
    snapshot = JsonlGraphStore().load(graph_path)
    engine = GraphQueryEngine(snapshot)
    result: dict[str, Any]
    if args.command == "task-closure":
        overlay = _read_object(graph_root / "task_overlay.json")
        closure_path = graph_root / "closure_overlay.json"
        closure = _read_object(closure_path) if closure_path.is_file() else None
        result = task_closure_result(
            engine=engine,
            overlay=overlay,
            closure=closure,
        )
    elif args.command == "bootstrap":
        result = engine.bootstrap(max_nodes=args.max_nodes)
    elif args.command == "search":
        result = engine.search(args.query, kinds=args.kind, limit=args.limit, offset=args.offset)
    elif args.command == "inspect":
        result = engine.inspect(args.node, neighbor_limit=args.neighbor_limit)
    elif args.command == "support":
        result = build_operational_support(
            engine,
            args.seeds,
            budget_tokens=args.budget_tokens,
            max_depth=args.max_depth,
            max_nodes=args.max_nodes,
        )
    elif args.command == "paths":
        result = engine.paths(
            args.source,
            args.target,
            max_depth=args.max_depth,
            max_paths=args.max_paths,
        )
    elif args.command == "closure":
        result = engine.closure(
            args.entrypoint,
            max_nodes=args.max_nodes,
            include_candidates=args.include_candidates,
        )
    elif args.command == "risks":
        result = engine.risks(args.node or None, limit=args.limit, offset=args.offset)
    elif args.command == "self-check":
        result = engine.self_check()
    else:
        raise ValueError(f"unsupported command: {args.command}")
    payload = response_payload(
        command=args.command,
        snapshot_id=snapshot.manifest.get("snapshot_id"),
        result=result,
        max_chars=max_chars,
    )
    rendered = dumps_response(payload)
    _append_query_audit(
        graph_root,
        payload,
        args=args,
        response_chars=len(rendered),
        max_chars=max_chars,
    )
    print(rendered)
    return 0 if result.get("valid", True) else 1


def _submission_command(args: argparse.Namespace) -> int:
    root = args.root.resolve() if args.root else _resolve_graph_root()
    submission = args.submission.resolve() if args.submission else _resolve_submission_dir()
    if args.command == "sync-submission":
        result = sync_submission(root, submission)
    elif args.command == "submission-check":
        sync = sync_submission(root, submission)
        result = compare_submission(root, submission)
        result["sync"] = {
            "revision": sync.get("revision", 0),
            "changed": sync.get("changed", False),
            "content_hash": sync.get("content_hash", ""),
        }
    else:
        result = compare_submission(root, submission)
    max_chars = _max_chars(args.command, args.max_chars)
    snapshot_id = None
    manifest_path = root / "base" / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        snapshot_id = manifest.get("snapshot_id") if isinstance(manifest, dict) else None
    payload = response_payload(
        command=args.command,
        snapshot_id=snapshot_id,
        result=result,
        max_chars=max_chars,
    )
    rendered = dumps_response(payload)
    _append_query_audit(
        root,
        payload,
        args=args,
        response_chars=len(rendered),
        max_chars=max_chars,
    )
    print(rendered)
    return 0


def _ledger_command(args: argparse.Namespace) -> int:
    root = args.root.resolve() if args.root else _resolve_graph_root()
    ledger = RepoGraphLedger(root)
    command = args.command
    if command == "claim":
        if args.ledger_action == "add":
            result = ledger.add_claim(
                subject=args.subject,
                predicate=args.predicate,
                object_value=args.object,
                classification=args.classification,
                confidence=args.confidence,
            )
        elif args.ledger_action == "update":
            result = ledger.update_claim(
                args.claim_id,
                status=args.status,
                evidence_ids=args.evidence,
                classification=args.classification,
            )
        else:
            result = {"claims": list(ledger.claim_states().values())}
        response_command = f"claim.{args.ledger_action}"
    elif command == "evidence":
        if args.ledger_action == "record":
            result = ledger.record_evidence(
                kind=args.kind,
                probe_type=args.probe_type,
                evidence_class=args.evidence_class,
                status=args.status,
                result_summary=args.result_summary,
                input_summary=args.input_summary,
                command=args.command_text,
                claim_ids=args.claim,
                affected_symbols=args.symbol,
            )
        else:
            result = {"evidence": list(ledger.evidence_states().values())}
        response_command = f"evidence.{args.ledger_action}"
    elif command == "freshness":
        result = ledger.freshness_report()
        response_command = command
    elif command == "stopping-check":
        result = ledger.stopping_guard()
        response_command = command
    else:
        detector_path = root / "risk_detectors.json"
        if not detector_path.is_file():
            raise ValueError("runtime risk detectors are available only in repo_graph_mode=evidence")
        result = json.loads(detector_path.read_text(encoding="utf-8"))
        response_command = command
    max_chars = _max_chars(command, args.max_chars)
    manifest = json.loads((root / "base" / "manifest.json").read_text(encoding="utf-8"))
    payload = response_payload(
        command=response_command,
        snapshot_id=manifest.get("snapshot_id") if isinstance(manifest, dict) else None,
        result=result,
        max_chars=max_chars,
    )
    rendered = dumps_response(payload)
    _append_query_audit(
        root,
        payload,
        args=args,
        response_chars=len(rendered),
        max_chars=max_chars,
    )
    print(rendered)
    return 0 if result.get("ready", True) else 1


def _resolve_graph_root() -> Path:
    configured = _configured_graph_root()
    if configured is not None:
        return configured
    agent_output = os.environ.get("FEATURELIFTBENCH_AGENT_OUTPUT_DIR", "").strip()
    if not agent_output:
        raise ValueError(
            f"graph path is required: pass --graph/--root or set {ROOT_ENV}"
        )
    return Path(agent_output).resolve() / "state" / "repo_graph"


def _configured_graph_root() -> Path | None:
    configured = os.environ.get(ROOT_ENV, "").strip()
    return Path(configured).resolve() if configured else None


def _resolve_submission_dir() -> Path:
    configured = os.environ.get("FEATURELIFTBENCH_SUBMISSION_DIR", "").strip()
    if not configured:
        raise ValueError("submission path is required: pass --submission or set FEATURELIFTBENCH_SUBMISSION_DIR")
    return Path(configured).resolve()


def _max_chars(command: str, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    if command == "inspect":
        configured_inspect = os.environ.get(INSPECT_MAX_CHARS_ENV, "").strip()
        if configured_inspect:
            try:
                return int(configured_inspect)
            except ValueError as exc:
                raise ValueError(f"{INSPECT_MAX_CHARS_ENV} must be an integer") from exc
    configured = os.environ.get(QUERY_MAX_CHARS_ENV, "").strip()
    if configured:
        try:
            return int(configured)
        except ValueError as exc:
            raise ValueError(f"{QUERY_MAX_CHARS_ENV} must be an integer") from exc
    return {
        "bootstrap": 6_000,
        "risks": 8_000,
        "inspect": 4_000,
        "support": 12_000,
    }.get(command, DEFAULT_QUERY_BUDGET)


def _append_query_audit(
    root: Path,
    payload: dict[str, Any],
    *,
    args: argparse.Namespace,
    response_chars: int,
    max_chars: int,
    status: str = "success",
    error: Exception | None = None,
) -> None:
    if not (root / "task_overlay.json").is_file() and not os.environ.get(
        "FEATURELIFTBENCH_AGENT_OUTPUT_DIR"
    ):
        return
    audit_path = root.parent.parent / "repo_graph_queries.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    parameters = _parameter_summary(args)
    row: dict[str, Any] = {
        "schema_version": payload.get("schema_version"),
        "command": payload.get("command"),
        "snapshot_id": payload.get("snapshot_id"),
        "truncated_by_budget": payload.get("truncated_by_budget", False),
        "result": {},
        "status": status,
        "timestamp_unix": round(time.time(), 6),
        "parameters": parameters,
        "parameter_digest": digest_json(parameters),
        "revision": _submission_revision(root),
        "response_chars": response_chars,
        "max_chars": max_chars,
        "result_digest": digest_json(payload.get("result", {})),
    }
    if error is not None:
        row["error_type"] = type(error).__name__
        row["error_message"] = _safe_error_message(error)
    with audit_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _audit_failure(args: argparse.Namespace, error: Exception) -> None:
    if getattr(args, "command", "") == "build":
        return
    root = _audit_root(args)
    if root is None:
        return
    snapshot_id = _snapshot_id(root)
    result = {"error": "command_failed", "error_type": type(error).__name__}
    payload = response_payload(
        command=str(getattr(args, "command", "unknown")),
        snapshot_id=snapshot_id,
        result=result,
        max_chars=512,
    )
    try:
        _append_query_audit(
            root,
            payload,
            args=args,
            response_chars=0,
            max_chars=_max_chars(str(getattr(args, "command", "")), getattr(args, "max_chars", None)),
            status="failed",
            error=error,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return


def _audit_root(args: argparse.Namespace) -> Path | None:
    explicit_root = getattr(args, "root", None)
    if isinstance(explicit_root, Path):
        return explicit_root.resolve()
    graph = getattr(args, "graph", None)
    if isinstance(graph, Path):
        graph_path = graph.resolve()
        return graph_path.parent if graph_path.name == "base" else graph_path
    try:
        return _resolve_graph_root()
    except ValueError:
        return None


def _snapshot_id(root: Path) -> str | None:
    manifest_path = root / "base" / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = _read_object(manifest_path)
    value = manifest.get("snapshot_id")
    return str(value) if value is not None else None


def _submission_revision(root: Path) -> int:
    state_path = root / "submission_state.json"
    if not state_path.is_file():
        return 0
    value = _read_object(state_path).get("revision", 0)
    return int(value) if isinstance(value, int) else 0


def _parameter_summary(args: argparse.Namespace) -> dict[str, Any]:
    blocked = {
        "command",
        "repo",
        "output",
        "graph",
        "root",
        "submission",
        "command_text",
        "input_summary",
        "result_summary",
        "object",
    }
    summary: dict[str, Any] = {}
    for key, value in sorted(vars(args).items()):
        if key in blocked or value is None or value is False or value == []:
            continue
        if isinstance(value, Path):
            summary[key] = "<configured-path>"
        elif isinstance(value, str):
            summary[key] = _safe_parameter_value(value)
        elif isinstance(value, list):
            summary[key] = [_safe_parameter_value(str(item)) for item in value[:20]]
        elif isinstance(value, (bool, int, float)):
            summary[key] = value
    return summary


def _safe_error_message(error: Exception) -> str:
    message = str(error).replace("\n", " ")[:256]
    for marker in ("api_key=", "token=", "password=", "secret="):
        if marker in message.lower():
            return "redacted potentially sensitive error"
    return message


def _safe_parameter_value(value: str) -> str:
    text = value[:128]
    lowered = text.lower()
    if any(marker in lowered for marker in ("api_key=", "token=", "password=", "secret=", "bearer ")):
        return "[REDACTED]"
    if re.search(r"\bsk-[A-Za-z0-9_-]{8,}\b", text):
        return "[REDACTED]"
    return text


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
