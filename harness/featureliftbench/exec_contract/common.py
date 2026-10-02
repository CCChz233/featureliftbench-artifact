"""Shared paths and projection helpers for exec_contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


RUNTIME_DIR = "runtime_traces"
CONTRACTS_DIR = "contracts"
FACTS_FILE = "RUNTIME_FACTS.md"
CONTRACT_INDEX = "CONTRACTS.md"
CONTRACT_FAILURES = "CONTRACT_FAILURES.md"
AUDIT_FILE = "exec_contract_phase.json"
TRACE_JSONL = "traces.jsonl"
PYTEST_REPORT = "pytest_report.json"
COLLECT_META = "collect_meta.json"
CLOSURE_CAPSULE_FILE = "CLOSURE_CAPSULE.json"

# Keep Phase0 cheap and on-target. One strongly ranked file is preferable to a
# broad suite: the collector is an evidence gate, not another benchmark run.
DEFAULT_MAX_TEST_FILES = 1
DEFAULT_COLLECT_TIMEOUT_SECONDS = 600
DEFAULT_VERIFY_TIMEOUT_SECONDS = 300
DEFAULT_REPAIR_ROUNDS = 1
DEFAULT_REPAIR_TIMEOUT_SECONDS = 1800

# Tokens that pollute keyword → test selection / watch prefixes.
KEYWORD_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "when",
        "from",
        "that",
        "this",
        "are",
        "was",
        "were",
        "been",
        "being",
        "have",
        "has",
        "had",
        "into",
        "onto",
        "over",
        "under",
        "only",
        "also",
        "such",
        "than",
        "then",
        "them",
        "they",
        "their",
        "there",
        "these",
        "those",
        "which",
        "while",
        "where",
        "whose",
        "what",
        "will",
        "would",
        "could",
        "should",
        "must",
        "may",
        "might",
        "can",
        "not",
        "without",
        "within",
        "between",
        "among",
        "about",
        "above",
        "after",
        "before",
        "below",
        "does",
        "did",
        "doing",
        "done",
        "each",
        "every",
        "other",
        "another",
        "same",
        "some",
        "any",
        "all",
        "both",
        "few",
        "more",
        "most",
        "other",
        "own",
        "too",
        "very",
        "just",
        "like",
        "via",
        "per",
        "api",
        "apis",
        "path",
        "paths",
        "kind",
        "kinds",
        "type",
        "types",
        "list",
        "lists",
        "dict",
        "tuple",
        "none",
        "true",
        "false",
        "return",
        "returns",
        "raise",
        "raises",
        "callable",
        "signature",
        "signatures",
        "package",
        "packages",
        "module",
        "modules",
        "class",
        "classes",
        "method",
        "methods",
        "function",
        "functions",
        "attribute",
        "attributes",
        "member",
        "members",
        "listed",
        "contract",
        "contracts",
        "featurelifted",
        "submission",
        "behavior",
        "behaviors",
        "required",
        "optional",
        "public",
        "hidden",
        "test",
        "tests",
        "using",
        "used",
        "uses",
        "use",
        "set",
        "sets",
        "get",
        "gets",
        "new",
        "old",
        "first",
        "second",
        "one",
        "two",
        "three",
    }
)

NOISE_FUNCS = frozenset(
    {
        "ApproxBase",
        "ApproxNumpy",
        "ApproxMapping",
        "ApproxSequenceLike",
        "ApproxScalar",
        "ApproxDecimal",
        "RaisesContext",
        "pytest_addoption",
        "pytest_configure",
        "pytest_sessionstart",
        "pytest_collection_modifyitems",
        "seed",
        "choices",
        "<module>",
        "__getattr__",
        "get",
        "getitem",
    }
)

DEMOTE_TEST_SUBSTR = (
    "mysql",
    "mssql",
    "postgresql",
    "postgres",
    "django",
    "oracle",
    "cockroach",
    "mariadb",
    "asyncio",
    "mypy",
    "typing",
)


def flatten_required_api(public_spec: dict[str, Any] | None) -> list[dict[str, str]]:
    """Return flat required API entries, preserving published signatures."""

    items: list[dict[str, str]] = []
    if not isinstance(public_spec, dict):
        return items

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        path = str(node.get("path") or "").strip()
        kind = str(node.get("kind") or "").strip()
        if path:
            item = {
                "path": path,
                "kind": kind or "symbol",
                "name": path.rsplit(".", 1)[-1],
            }
            signature = str(node.get("signature") or "").strip()
            if signature:
                item["signature"] = signature
            items.append(item)
        for member in node.get("members") or []:
            walk(member)

    for entry in public_spec.get("required_api") or []:
        walk(entry)
    return items


def behavior_texts(public_spec: dict[str, Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(public_spec, dict):
        return out
    for behavior in public_spec.get("behaviors") or []:
        if not isinstance(behavior, dict):
            continue
        bid = str(behavior.get("id") or "").strip()
        text = str(behavior.get("text") or "").strip()
        if bid or text:
            out.append({"id": bid, "text": text})
    return out


def source_entrypoint_names(public_spec: dict[str, Any] | None) -> list[str]:
    if not isinstance(public_spec, dict):
        return []
    out: list[str] = []
    for ep in public_spec.get("source_entrypoints") or []:
        text = str(ep).strip()
        if text:
            out.append(text)
    return out


def keywords_from_public_spec(public_spec: dict[str, Any] | None) -> list[str]:
    """Keywords used to select upstream tests (stopwords stripped)."""

    keys: set[str] = set()
    for item in flatten_required_api(public_spec):
        name = item["name"]
        if name and len(name) >= 3:
            keys.add(name.lower())
        for part in item["path"].split("."):
            if part and part != "featurelifted" and len(part) >= 3:
                keys.add(part.lower())
    for ep in source_entrypoint_names(public_spec):
        for part in ep.split("."):
            if part and len(part) >= 3:
                keys.add(part.lower())
    for behavior in behavior_texts(public_spec):
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", behavior.get("text") or ""):
            keys.add(token.lower())
    title = ""
    if isinstance(public_spec, dict):
        title = str(public_spec.get("title") or "")
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", title):
        keys.add(token.lower())

    return sorted(k for k in keys if k not in KEYWORD_STOPWORDS and len(k) >= 3)


def is_noise_event(
    event: dict[str, Any],
    *,
    allow_path_prefixes: list[str] | tuple[str, ...] | None = None,
) -> bool:
    func = str(event.get("func") or "")
    args = event.get("args")
    if (
        func[:1].isupper()
        and isinstance(args, dict)
        and not args
        and not event.get("owner")
    ):
        return True
    if (
        func.startswith("__")
        and func.endswith("__")
        and func != "__init__"
    ):
        return True
    if func in NOISE_FUNCS:
        return True
    path = str(event.get("file") or event.get("qualname") or "")
    norm = path.replace("\\", "/")
    if allow_path_prefixes and any(
        prefix in norm for prefix in allow_path_prefixes
    ):
        return False
    if any(
        bad in norm
        for bad in (
            "/_pytest/",
            "/pytest/",
            "/pluggy/",
            "/site-packages/_pytest/",
            "/site-packages/pluggy/",
            "/_vendor/",
            "/vendor/",
        )
    ):
        return True
    return False


def project_value(value: Any, *, depth: int = 0, max_depth: int = 3) -> Any:
    """JSON-safe projection of runtime values for contracts."""

    if depth > max_depth:
        return "<max_depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > 200:
            return value[:200] + "…"
        return value
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, (list, tuple)):
        if len(value) > 20:
            return [project_value(v, depth=depth + 1) for v in value[:20]] + ["…"]
        return [project_value(v, depth=depth + 1) for v in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= 20:
                out["…"] = f"+{len(value) - 20} keys"
                break
            out[str(k)[:80]] = project_value(v, depth=depth + 1)
        return out
    text = repr(value)
    if len(text) > 120:
        text = text[:120] + "…"
    return {"__repr__": text, "__type__": type(value).__name__}


def dumps_pretty(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=str) + "\n"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def scaled_collect_timeout(num_tests: int, base: int = DEFAULT_COLLECT_TIMEOUT_SECONDS) -> int:
    """Wall budget for Phase0. Default path uses --no-trace (faster); keep a floor."""

    n = max(1, int(num_tests))
    # Without settrace, 90s/file is usually enough; keep prior floor for flaky installs.
    return int(min(720, max(base, 90 * n)))
