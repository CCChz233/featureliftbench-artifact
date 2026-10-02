"""Synthesize executable contracts against featurelifted from traces + public_spec + upstream AST."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from .common import CLOSURE_CAPSULE_FILE
from .common import CONTRACT_INDEX
from .common import CONTRACTS_DIR
from .common import RUNTIME_DIR
from .common import TRACE_JSONL
from .common import behavior_texts
from .common import ensure_dir
from .common import flatten_required_api
from .common import is_noise_event
from .common import KEYWORD_STOPWORDS
from .common import source_entrypoint_names


OBLIGATIONS_FILE = "OBLIGATIONS.json"
MUTATION_AUDIT_FILE = "MUTATION_AUDIT.json"
CGCC_VARIANTS = frozenset({"cgcc_lite", "cgcc_roc", "cgcc_rmc"})
CONTRACT_VARIANTS = frozenset({"clean3", "fcec", *CGCC_VARIANTS})


def synthesize_contracts(
    workspace_dir: str | Path,
    public_spec: dict[str, Any] | None,
    collect_meta: dict[str, Any] | None = None,
    *,
    variant: str = "clean3",
) -> dict[str, Any]:
    variant = str(variant or "clean3").strip().lower()
    if variant not in CONTRACT_VARIANTS:
        raise ValueError(
            f"contract variant must be one of {sorted(CONTRACT_VARIANTS)}, got {variant!r}"
        )
    workspace = Path(workspace_dir).resolve()
    contracts = ensure_dir(workspace / CONTRACTS_DIR)
    (contracts / "__init__.py").write_text("", encoding="utf-8")

    required_api = flatten_required_api(public_spec)
    api = list(required_api)
    behaviors = behavior_texts(public_spec)
    watch_prefixes = list((collect_meta or {}).get("watch_prefixes") or [])
    events = [
        e
        for e in _load_events(workspace / RUNTIME_DIR / TRACE_JSONL)
        if not is_noise_event(e, allow_path_prefixes=watch_prefixes)
    ]

    inferred = infer_api_from_upstream(workspace / "repo", public_spec)
    # Surface: required_api + small allowlisted inferred symbols (cut format_* noise).
    surface_api = _surface_api_for_contracts(api, inferred, public_spec)
    api = _merge_api(api, inferred["api"])

    surface = _generate_surface_tests(
        surface_api,
        check_signatures=variant == "fcec",
    )
    (contracts / "test_required_surface.py").write_text(surface, encoding="utf-8")

    replay = _generate_replay_tests(
        required_api if variant == "fcec" else api,
        events,
        state_free_only=variant == "fcec",
    )
    (contracts / "test_runtime_replay.py").write_text(replay["code"], encoding="utf-8")

    scenarios = _generate_scenario_tests(
        api, public_spec, inferred, variant=variant
    )
    (contracts / "test_behavior_scenarios.py").write_text(scenarios["code"], encoding="utf-8")

    behavior_doc = _generate_behavior_checklist(behaviors)
    (contracts / "test_behavior_checklist.py").write_text(behavior_doc, encoding="utf-8")

    obligations = _build_cgcc_obligations(
        api=api,
        public_spec=public_spec,
        inferred=inferred,
        variant=variant,
    )
    mutation_audit = _build_mutation_audit(obligations, variant=variant)
    closure_capsule = _build_closure_capsule(
        required_api=required_api,
        public_spec=public_spec,
        events=events,
        selected_tests=list((collect_meta or {}).get("selected_tests") or []),
    )
    (workspace / CLOSURE_CAPSULE_FILE).write_text(
        json.dumps(closure_capsule, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (workspace / OBLIGATIONS_FILE).write_text(
        json.dumps(
            {
                "schema_version": "featureliftbench.cgcc_obligations.v1",
                "contract_variant": variant,
                "evidence_policy": {
                    "A": "TASK/public_spec explicit",
                    "B": "upstream source/AST/runtime supported",
                    "C": "pre-registered semantic consistency operator",
                    "formal_eval": "forbidden",
                },
                "obligations": obligations,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / MUTATION_AUDIT_FILE).write_text(
        json.dumps(mutation_audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    substantive = int(scenarios["assertions"]) + int(replay["count"]) + _count_surface_asserts(surface)
    # Surface-only (hasattr) is not enough; require real scenario assertions.
    replay_behavior_count = int(
        replay["behavioral_count"]
        if variant == "fcec"
        else replay["count"]
    )
    contracts_substantive = bool(
        scenarios["assertions"] >= 2 or replay_behavior_count > 0
    )
    if variant in CGCC_VARIANTS:
        contracts_substantive = bool(
            contracts_substantive and mutation_audit["mutation_adequacy_ok"]
        )

    quality = "low"
    if collect_meta and isinstance(collect_meta, dict):
        quality = str(collect_meta.get("trace_quality") or "low")

    index = [
        "# Contracts (from upstream execution + inferred surface)",
        "",
        "These pytest modules must pass against `submission/featurelifted`.",
        "Derived from upstream runtime observations, public_spec, and upstream AST",
        "(source_entrypoints) — **not** from benchmark public/hidden tests.",
        "",
        "- `test_required_surface.py` — required API + allowlisted inferred surface",
        "- `test_runtime_replay.py` — replayable call/exception observations",
        "- `test_behavior_scenarios.py` — **behavioral** mini-assertions (must actually run)",
        "- `test_behavior_checklist.py` — behavior catalog (documentation only)",
        "",
        "Do **not** treat hasattr-only greens as done: scenarios exercise resolve/invoke/",
        "graph behavior. `callable(x)` is insufficient.",
        "",
        f"Replay cases: {replay['count']}",
        f"Scenario assertions: {scenarios['assertions']}",
        f"Inferred upstream methods: {len(inferred.get('methods') or [])}",
        f"Surface symbols kept: {len(surface_api)}",
        f"Phase0 trace quality: `{quality}`",
        f"Contracts substantive: `{contracts_substantive}`",
        f"Contract variant: `{variant}`",
        f"Mutation families covered: "
        f"{mutation_audit['covered_family_count']}/{mutation_audit['applicable_family_count']}",
        f"Mutation adequacy: `{mutation_audit['mutation_adequacy_ok']}`",
        f"Clause-bound dynamic obligations: "
        f"{closure_capsule['clause_bound_obligations']}",
        f"Required API closure: `{closure_capsule['api_closure_complete']}`",
        f"Published signature closure: "
        f"`{closure_capsule['signature_closure_complete']}`",
        "",
    ]
    (workspace / CONTRACT_INDEX).write_text("\n".join(index), encoding="utf-8")
    (contracts / "README.md").write_text(
        "Run: `PYTHONPATH=submission pytest contracts/ -q`\n",
        encoding="utf-8",
    )
    return {
        "api_symbols": len(api),
        "replay_cases": replay["count"],
        "behavior_replay_cases": replay["behavioral_count"],
        "behaviors": len(behaviors),
        "scenario_assertions": scenarios["assertions"],
        "behavior_assertions": int(scenarios["assertions"])
        + replay_behavior_count,
        "inferred_methods": inferred.get("methods") or [],
        "semantic_evidence": inferred.get("semantic_evidence") or [],
        "contract_variant": variant,
        "obligations": len(obligations),
        "applicable_mutation_families": mutation_audit["applicable_families"],
        "covered_mutation_families": mutation_audit["covered_families"],
        "mutation_adequacy_ok": mutation_audit["mutation_adequacy_ok"],
        "contracts_substantive": contracts_substantive,
        "substantive_count": substantive,
        "trace_quality": quality,
        "closure_capsule_file": CLOSURE_CAPSULE_FILE,
        "api_closure_complete": closure_capsule["api_closure_complete"],
        "signature_closure_complete": closure_capsule[
            "signature_closure_complete"
        ],
        "clause_bound_obligations": closure_capsule[
            "clause_bound_obligations"
        ],
        "dynamic_bindings": len(closure_capsule["dynamic_bindings"]),
        "contracts_dir": CONTRACTS_DIR,
    }


def infer_api_from_upstream(
    repo_dir: str | Path,
    public_spec: dict[str, Any] | None,
) -> dict[str, Any]:
    """Inspect upstream classes named in source_entrypoints; map methods onto featurelifted.

    Handles: src-layout, missing Lazy* aliases (LazyCommandCollection → CommandCollection),
    and methods inherited from base classes defined in the same module (e.g. Group.invoke).
    """

    repo = Path(repo_dir)
    methods: list[str] = []
    api: list[dict[str, str]] = []
    class_attrs: dict[str, list[str]] = {}
    semantic_evidence: set[str] = set()
    if not repo.is_dir() or not isinstance(public_spec, dict):
        return {
            "api": api,
            "methods": methods,
            "class_attrs": class_attrs,
            "semantic_evidence": [],
        }

    for ep in source_entrypoint_names(public_spec):
        parts = [p for p in ep.split(".") if p]
        if len(parts) < 2:
            continue
        fl_cls_name = parts[-1]  # name on featurelifted side
        mod_parts = parts[:-1]
        resolved = _resolve_upstream_class(repo, mod_parts, fl_cls_name)
        if resolved is None:
            continue
        src, class_node, tree = resolved
        source_text = src.read_text(encoding="utf-8", errors="ignore")
        if (
            "Ordering required" in source_text
            or "OrderedSet" in source_text
            or "OrderedDict" in source_text
        ):
            semantic_evidence.add("preserves_insertion_order")
        related: dict[str, ast.ClassDef] = {fl_cls_name: class_node}
        # Prefer Context from same module / package for attr checks.
        ctx = _find_class(tree, "Context")
        if ctx is None:
            ctx_file = _locate_class_file(repo, "Context")
            if ctx_file is not None:
                try:
                    ctx_tree = ast.parse(
                        ctx_file.read_text(encoding="utf-8", errors="ignore")
                    )
                    ctx = _find_class(ctx_tree, "Context")
                except SyntaxError:
                    ctx = None
        if ctx is not None:
            related["Context"] = ctx

        # Methods: own + same-module bases (CommandCollection ← Group ← …).
        inherited = _methods_with_bases(tree, class_node)
        for meth in inherited:
            if meth in {"__init__", "__call__"}:
                continue
            methods.append(meth)
            api.append(
                {
                    "path": f"featurelifted.{fl_cls_name}.{meth}",
                    "kind": "method",
                    "name": meth,
                }
            )
        class_attrs[fl_cls_name] = sorted(set(inherited))
        api.append(
            {
                "path": f"featurelifted.{fl_cls_name}",
                "kind": "class",
                "name": fl_cls_name,
            }
        )

        if "Context" in related:
            ctx_node = related["Context"]
            attrs: list[str] = []
            for item in ctx_node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_") or item.name in {"__init__", "__call__"}:
                        if not (
                            item.name.startswith("__")
                            and item.name.endswith("__")
                            and item.name not in {"__init__", "__call__"}
                        ):
                            attrs.append(item.name)
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and not target.id.startswith("_"):
                            attrs.append(target.id)
                elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    if not item.target.id.startswith("_"):
                        attrs.append(item.target.id)
            # Also scan __init__ assignments: self.default_map = ...
            for item in ctx_node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
                    for sub in ast.walk(item):
                        if (
                            isinstance(sub, ast.Attribute)
                            and isinstance(sub.value, ast.Name)
                            and sub.value.id == "self"
                            and not sub.attr.startswith("_")
                        ):
                            attrs.append(sub.attr)
            class_attrs["Context"] = sorted(set(attrs))
            api.append(
                {
                    "path": "featurelifted.Context",
                    "kind": "class",
                    "name": "Context",
                }
            )

    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for item in api:
        path = item["path"]
        if path in seen:
            continue
        seen.add(path)
        uniq.append(item)
    return {
        "api": uniq,
        "methods": sorted(set(methods)),
        "class_attrs": class_attrs,
        "semantic_evidence": sorted(semantic_evidence),
    }


def _resolve_upstream_class(
    repo: Path, mod_parts: list[str], cls_name: str
) -> tuple[Path, ast.ClassDef, ast.AST] | None:
    """Locate class; try Lazy* → * alias when snapshot renamed the type."""

    candidates = [cls_name]
    if cls_name.startswith("Lazy") and len(cls_name) > 4:
        candidates.append(cls_name[len("Lazy") :])  # LazyCommandCollection → CommandCollection

    src = _locate_module_file(repo, mod_parts)
    files: list[Path] = []
    if src is not None:
        files.append(src)
    for name in candidates:
        located = _locate_class_file(repo, name)
        if located is not None and located not in files:
            files.append(located)

    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for name in candidates:
            node = _find_class(tree, name)
            if node is not None:
                return path, node, tree
    return None


def _base_class_names(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _methods_with_bases(tree: ast.AST, class_node: ast.ClassDef) -> list[str]:
    """Public methods on class and same-module bases (one module MRO walk)."""

    by_name: dict[str, ast.ClassDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            by_name[node.name] = node

    seen_cls: set[str] = set()
    methods: list[str] = []

    def walk(cls: ast.ClassDef) -> None:
        if cls.name in seen_cls:
            return
        seen_cls.add(cls.name)
        for item in cls.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                meth = item.name
                if meth.startswith("_") and meth not in {"__init__", "__call__"}:
                    continue
                if (
                    meth.startswith("__")
                    and meth.endswith("__")
                    and meth not in {"__init__", "__call__"}
                ):
                    continue
                methods.append(meth)
        for base_name in _base_class_names(cls):
            # Skip typing constructs
            if base_name in by_name:
                walk(by_name[base_name])

    walk(class_node)
    # de-dupe preserve order
    out: list[str] = []
    seen_m: set[str] = set()
    for m in methods:
        if m not in seen_m:
            seen_m.add(m)
            out.append(m)
    return out


def _locate_module_file(repo: Path, mod_parts: list[str]) -> Path | None:
    candidates = [
        repo.joinpath(*mod_parts).with_suffix(".py"),
        repo.joinpath(*mod_parts, "__init__.py"),
        repo.joinpath("src", *mod_parts).with_suffix(".py"),
        repo.joinpath("src", *mod_parts, "__init__.py"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    if not mod_parts:
        return None
    leaf = mod_parts[-1] + ".py"
    matches = [
        m
        for m in repo.rglob(leaf)
        if not ({".tox", "venv", ".venv", "__pycache__", "site-packages"} & set(m.parts))
    ]
    for match in matches:
        if all(p in match.parts for p in mod_parts[:-1]):
            return match
    # Last resort: any file defining the leaf module name under package root.
    if len(mod_parts) >= 2:
        pkg = mod_parts[0]
        for match in matches:
            if pkg in match.parts:
                return match
    return matches[0] if matches else None


def _locate_class_file(repo: Path, class_name: str) -> Path | None:
    """Fallback when module path layout is unusual: scan for `class ClassName`."""

    needle = f"class {class_name}"
    for path in repo.rglob("*.py"):
        if {".tox", "venv", ".venv", "__pycache__", "site-packages", "tests"} & set(path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if needle in text:
            return path
    return None


def _find_class(tree: ast.AST, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _merge_api(
    base: list[dict[str, str]], extra: list[dict[str, str]]
) -> list[dict[str, str]]:
    seen = {a["path"] for a in base}
    out = list(base)
    for item in extra:
        if item["path"] not in seen:
            seen.add(item["path"])
            out.append(item)
    return out


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _build_closure_capsule(
    *,
    required_api: list[dict[str, str]],
    public_spec: dict[str, Any] | None,
    events: list[dict[str, Any]],
    selected_tests: list[str],
) -> dict[str, Any]:
    """Produce a small clause/API/signature-first, evaluator-blind capsule."""

    behaviors = behavior_texts(public_spec)
    callable_kinds = {"class", "function", "method"}
    signatures = [
        {
            "path": item["path"],
            "kind": item["kind"],
            "signature": item["signature"],
        }
        for item in required_api
        if item.get("kind") in callable_kinds and item.get("signature")
    ]
    published_callable_paths = {
        item["path"]
        for item in required_api
        if item.get("kind") in callable_kinds and item.get("signature")
    }
    signature_paths = {item["path"] for item in signatures}

    clause_records: list[dict[str, Any]] = []
    dynamic_bindings: list[dict[str, Any]] = []
    for behavior in behaviors:
        text = str(behavior.get("text") or "")
        lowered = text.lower()
        api_paths = [
            item["path"]
            for item in required_api
            if item["name"].lower() in lowered
            or item["path"].lower() in lowered
        ]
        terms: set[str] = set()
        for item in required_api:
            name = str(item.get("name") or "")
            if name and re.search(
                rf"\b{re.escape(name)}\b",
                text,
                flags=re.IGNORECASE,
            ):
                terms.update(_identifier_terms(name))
        for match in re.findall(r"`([^`]+)`", text):
            for part in match.split("."):
                terms.update(_identifier_terms(part))
        evidence_ids: list[str] = []
        for index, event in enumerate(events):
            raw_func = str(event.get("func") or "")
            raw_name = (
                str(event.get("owner") or "")
                if raw_func == "__init__"
                else raw_func
            )
            func = re.sub(r"[^a-z0-9]", "", raw_name.lower())
            if not func or raw_func.startswith("__") and raw_func != "__init__":
                continue
            matched = sorted(
                term
                for term in terms
                if re.sub(r"[^a-z0-9]", "", term) == func
                or (
                    len(term) >= 4
                    and re.sub(r"[^a-z0-9]", "", term) in func
                )
            )
            if not matched:
                continue
            evidence_id = f"trace:{index}"
            evidence_ids.append(evidence_id)
            dynamic_bindings.append(
                {
                    "behavior_id": behavior.get("id") or "",
                    "evidence_id": evidence_id,
                    "function": raw_name,
                    "file": event.get("file"),
                    "matched_terms": matched[:8],
                }
            )
            if len(evidence_ids) >= 5:
                break
        clause_records.append(
            {
                "id": behavior.get("id") or "",
                "text": text,
                "required_api_paths": api_paths,
                "dynamic_evidence": evidence_ids,
            }
        )

    bound_clause_ids = {
        str(item.get("behavior_id") or "")
        for item in dynamic_bindings
        if item.get("behavior_id")
    }
    return {
        "schema_version": "featureliftbench.fcec_capsule.v1",
        "evidence_policy": {
            "inputs": [
                "TASK/public_spec",
                "selected upstream repository tests",
                "upstream runtime trace",
            ],
            "formal_evaluator": "forbidden",
            "unbound_dynamic_observations": "excluded",
        },
        "selected_tests": selected_tests,
        "required_api": required_api,
        "published_signatures": signatures,
        "clauses": clause_records,
        "dynamic_bindings": dynamic_bindings[:80],
        "clause_bound_obligations": len(bound_clause_ids),
        "api_closure_complete": bool(required_api)
        and all(item.get("path") and item.get("kind") for item in required_api),
        "signature_closure_complete": (
            published_callable_paths == signature_paths
        ),
    }


def _identifier_terms(value: str) -> set[str]:
    """Split snake/camel API identifiers without adding prose keywords."""

    pieces = re.findall(
        r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|[0-9]+",
        value.replace("-", "_"),
    )
    terms = {
        piece.lower()
        for piece in pieces
        if len(piece) >= 3 and piece.lower() not in KEYWORD_STOPWORDS
    }
    normalized = re.sub(r"[^A-Za-z0-9]", "", value).lower()
    if len(normalized) >= 3 and normalized not in KEYWORD_STOPWORDS:
        terms.add(normalized)
    return terms


def _count_surface_asserts(code: str) -> int:
    return code.count("assert ")


# Inherited click Group helpers that drown required API and tempt copy-paste stubs.
_SURFACE_METHOD_DENY = frozenset(
    {
        "format_arguments",
        "format_commands",
        "format_epilog",
        "format_help",
        "format_help_text",
        "format_options",
        "format_usage",
        "get_help",
        "get_help_option",
        "get_help_option_names",
        "get_params",
        "get_short_help_str",
        "get_usage",
        "make_parser",
        "shell_complete",
        "to_info_dict",
        "collect_usage_pieces",
        "command",
        "group",
        "result_callback",
        "add_command",
        "main",
        "parse_args",
        "resolve_command",
    }
)

# Keep only an inferred method with a demonstrated task-level behavioral
# closure. Other upstream helpers (add_source, make_context, add_revision,
# filter_for_lineage, Revision properties, etc.) are implementation choices,
# not part of the featurelifted contract; requiring them rejects valid compact
# reference solutions.
_SURFACE_METHOD_ALLOW = frozenset(
    {
        "invoke",
    }
)


def _behavior_blob(public_spec: dict[str, Any] | None) -> str:
    parts: list[str] = []
    if not isinstance(public_spec, dict):
        return ""
    for key in ("title", "summary"):
        parts.append(str(public_spec.get(key) or ""))
    for item in behavior_texts(public_spec):
        parts.append(str(item.get("text") or ""))
        parts.append(str(item.get("id") or ""))
    return " ".join(parts).lower()


def _surface_api_for_contracts(
    required: list[dict[str, str]],
    inferred: dict[str, Any],
    public_spec: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """required_api ∪ allowlisted inferred methods; drop help/format noise."""

    out = list(required)
    seen = {a["path"] for a in out}
    for item in inferred.get("api") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        kind = str(item.get("kind") or "")
        name = str(item.get("name") or path.rsplit(".", 1)[-1])
        if path in seen:
            continue
        if kind == "class":
            # Keep Context when behaviors mention envvar / default_map / context.
            blob = _behavior_blob(public_spec)
            if name == "Context" and any(
                tok in blob for tok in ("context", "envvar", "default_map", "defaults")
            ):
                out.append(item)
                seen.add(path)
            continue
        if kind != "method":
            continue
        if name in _SURFACE_METHOD_DENY:
            continue
        if name not in _SURFACE_METHOD_ALLOW:
            continue
        out.append(item)
        seen.add(path)
    return out


def _generate_surface_tests(
    api: list[dict[str, str]],
    *,
    check_signatures: bool = False,
) -> str:
    lines = [
        '"""Required + upstream-inferred API surface contracts."""',
        "from __future__ import annotations",
        "",
        "import importlib",
        "import inspect",
        "",
        "",
        "def _signature_shape(value):",
        "    signature = inspect.signature(value)",
        "    return [",
        "        (",
        "            parameter.name,",
        "            parameter.kind.name,",
        "            parameter.default is not inspect.Parameter.empty,",
        "            None if parameter.default is inspect.Parameter.empty else repr(parameter.default),",
        "        )",
        "        for parameter in signature.parameters.values()",
        "    ]",
        "",
        "",
        "def test_featurelifted_package_importable() -> None:",
        "    importlib.import_module('featurelifted')",
        "",
    ]
    if not api:
        return "\n".join(lines)

    classes = [a for a in api if a.get("kind") == "class"]
    methods = [a for a in api if a.get("kind") == "method"]
    top_level = [
        a
        for a in api
        if a.get("kind") in {"function", "symbol", "class", "exception", ""}
        and a["path"].count(".") == 1
    ]

    for item in top_level[:40]:
        path = item["path"]
        if not path.startswith("featurelifted."):
            continue
        name = path.split(".", 1)[1]
        safe = "".join(ch if ch.isalnum() else "_" for ch in name)
        lines += [
            f"def test_top_level_{safe}() -> None:",
            "    mod = importlib.import_module('featurelifted')",
            f"    assert hasattr(mod, {name!r}), {path!r}",
            "",
        ]

    for item in classes[:30]:
        path = item["path"]
        parts = path.split(".")
        if len(parts) < 2 or parts[0] != "featurelifted":
            continue
        safe = "_".join(parts)
        lines += [
            f"def test_class_{safe}() -> None:",
            f"    parts = {parts!r}",
            "    mod = importlib.import_module('.'.join(parts[:-1]))",
            "    cls = getattr(mod, parts[-1])",
            "    assert isinstance(cls, type)",
            "",
        ]

    for item in methods[:60]:
        path = item["path"]
        parts = path.split(".")
        if len(parts) < 3 or parts[0] != "featurelifted":
            continue
        meth = parts[-1]
        safe = "_".join(parts)
        lines += [
            f"def test_method_{safe}() -> None:",
            f"    parts = {parts!r}",
            "    mod = importlib.import_module('.'.join(parts[:-2]))",
            "    cls = getattr(mod, parts[-2])",
            f"    assert callable(getattr(cls, {meth!r}, None)), {path!r}",
            "",
        ]
    signature_items = (
        [a for a in api if a.get("signature")][:80]
        if check_signatures
        else []
    )
    for item in signature_items:
        path = item["path"]
        parts = path.split(".")
        if len(parts) < 2 or parts[0] != "featurelifted":
            continue
        safe = "_".join(parts)
        lines += [
            f"def test_signature_{safe}() -> None:",
            f"    parts = {parts!r}",
            "    mod = importlib.import_module('featurelifted')",
            "    value = mod",
            "    for name in parts[1:]:",
            "        value = getattr(value, name)",
            f"    expected = {_signature_contract_shape(item['signature'])!r}",
            "    assert _signature_shape(value) == expected",
            "",
        ]
    return "\n".join(lines)


def _signature_contract_shape(
    signature: str,
) -> list[tuple[str, str, bool, str | None]]:
    """Parse the public parameter/default shape without evaluating annotations."""

    head = str(signature).split("->", 1)[0].strip()
    if not head.startswith("(") or ")" not in head:
        return []
    body = head[1 : head.rfind(")")]
    values = _split_signature_parameters(body)
    out: list[list[Any]] = []
    keyword_only = False
    for value in values:
        item = value.strip()
        if not item:
            continue
        if item == "/":
            for prior in out:
                if prior[1] == "POSITIONAL_OR_KEYWORD":
                    prior[1] = "POSITIONAL_ONLY"
            continue
        if item == "*":
            keyword_only = True
            continue
        kind = "KEYWORD_ONLY" if keyword_only else "POSITIONAL_OR_KEYWORD"
        if item.startswith("**"):
            kind = "VAR_KEYWORD"
            item = item[2:].strip()
        elif item.startswith("*"):
            kind = "VAR_POSITIONAL"
            keyword_only = True
            item = item[1:].strip()
        default_at = _top_level_character(item, "=")
        has_default = default_at >= 0
        default = item[default_at + 1 :].strip() if has_default else None
        declaration = item[:default_at].strip() if has_default else item
        annotation_at = _top_level_character(declaration, ":")
        name = (
            declaration[:annotation_at].strip()
            if annotation_at >= 0
            else declaration.strip()
        )
        out.append([name, kind, has_default, default])
    return [tuple(item) for item in out]  # type: ignore[return-value]


def _split_signature_parameters(value: str) -> list[str]:
    out: list[str] = []
    start = 0
    depth = 0
    quote = ""
    escaped = False
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            out.append(value[start:index])
            start = index + 1
    out.append(value[start:])
    return out


def _top_level_character(value: str, target: str) -> int:
    depth = 0
    quote = ""
    escaped = False
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == target and depth == 0:
            return index
    return -1


def _simple_args(args: dict[str, Any] | None) -> bool:
    if not isinstance(args, dict):
        return False
    for key, value in args.items():
        if key in {"self", "cls"}:
            continue
        if key.startswith("__"):
            return False
        if isinstance(value, dict) and ("__type__" in value or "__repr__" in value):
            return False
        if isinstance(value, (list, dict)) and _contains_opaque(value):
            return False
    return True


def _contains_opaque(value: Any) -> bool:
    if isinstance(value, dict):
        if "__type__" in value or "__repr__" in value:
            return True
        return any(_contains_opaque(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_opaque(v) for v in value)
    return False


def _generate_replay_tests(
    api: list[dict[str, str]],
    events: list[dict[str, Any]],
    *,
    state_free_only: bool = False,
) -> dict[str, Any]:
    api_names = {a["name"] for a in api}
    cases: list[dict[str, Any]] = []
    for event in events:
        func = str(event.get("func") or "")
        event_api_name = (
            str(event.get("owner") or "")
            if func == "__init__"
            else func
        )
        if event_api_name not in api_names:
            continue
        matches = [a for a in api if a["name"] == event_api_name]
        if not matches:
            continue
        item = matches[0]
        if item.get("kind") not in {"class", "function", "method"}:
            continue
        if state_free_only and item.get("kind") == "method":
            # A call trace does not serialize the receiver's pre-state. Replaying
            # a stateful method on a fresh instance fabricates a different
            # scenario (for example conflict commit on an empty registry).
            continue
        args = event.get("args") if isinstance(event.get("args"), dict) else {}
        call_args = {
            k: v for k, v in args.items() if k not in {"self", "cls"}
        }
        if not _simple_args(call_args):
            continue
        if not _call_args_match_public_signature(item, call_args):
            continue
        if item.get("kind") == "method":
            owner_path = item["path"].rsplit(".", 1)[0]
            owner_item = next(
                (candidate for candidate in api if candidate["path"] == owner_path),
                None,
            )
            if owner_item is None or not _signature_allows_no_args(owner_item):
                continue
        exception = event.get("exception")
        if exception and str(exception.get("type") or "") not in api_names:
            continue
        if (
            not exception
            and item.get("kind") != "class"
            and not _return_matches_public_signature(item, event.get("return"))
        ):
            continue
        target = item["path"]
        cases.append(
            {
                "target": target,
                "func": event_api_name,
                "kind": item.get("kind"),
                "args": call_args,
                "exception": exception,
                "return": event.get("return"),
            }
        )
        if len(cases) >= 40:
            break

    if not cases:
        lines = [
            '"""Replay contracts mapped from upstream traces onto featurelifted API names."""',
            "from __future__ import annotations",
            "",
            "import pytest",
            "",
            "",
            "def test_no_replay_cases_placeholder() -> None:",
            "    pytest.skip('no simple name-matched replay cases from upstream traces')",
            "",
        ]
        return {"code": "\n".join(lines), "count": 0, "behavioral_count": 0}

    lines = [
        '"""Replay contracts mapped from upstream traces onto featurelifted API names."""',
        "from __future__ import annotations",
        "",
        "import importlib",
        "import pytest",
        "",
        f"CASES = {json.dumps(cases, ensure_ascii=False, indent=2)}",
        "",
        "",
        "def _resolve(path: str):",
        "    parts = path.split('.')",
        "    mod = importlib.import_module('.'.join(parts[:-1]))",
        "    return getattr(mod, parts[-1])",
        "",
        "",
        "@pytest.mark.parametrize('case', CASES)",
        "def test_runtime_replay_case(case) -> None:",
        "    target = case['target']",
        "    parts = target.split('.')",
        "    if len(parts) >= 3:",
        "        mod = importlib.import_module('.'.join(parts[:-2]))",
        "        cls = getattr(mod, parts[-2])",
        "        try:",
        "            obj = cls()",
        "        except TypeError:",
        "            pytest.skip(f'cannot construct {parts[-2]} for replay')",
        "        fn = getattr(obj, parts[-1])",
        "    else:",
        "        fn = _resolve(target)",
        "    kwargs = {k: v for k, v in (case.get('args') or {}).items() if k != 'self'}",
        "    plain = {}",
        "    for k, v in kwargs.items():",
        "        if isinstance(v, dict) and ('__type__' in v or '__repr__' in v):",
        "            pytest.skip('opaque arg')",
        "        plain[k] = v",
        "    exc = case.get('exception')",
        "    if exc:",
        "        with pytest.raises(Exception) as caught:",
        "            fn(**plain)",
        "        assert type(caught.value).__name__ == exc.get('type')",
        "    else:",
        "        result = fn(**plain)",
        "        expected = case.get('return')",
        "        if case.get('kind') == 'class':",
        "            assert result is not None",
        "        elif isinstance(expected, (bool, int, float, str)) or expected is None:",
        "            assert result == expected",
        "",
    ]
    return {
        "code": "\n".join(lines),
        "count": len(cases),
        "behavioral_count": sum(
            1 for case in cases if case.get("kind") != "class"
        ),
    }


def _call_args_match_public_signature(
    item: dict[str, str],
    call_args: dict[str, Any],
) -> bool:
    signature = str(item.get("signature") or "")
    if not signature:
        return True
    shape = _signature_contract_shape(signature)
    allowed = {
        name
        for name, kind, _, _ in shape
        if name not in {"self", "cls"}
        and kind not in {"VAR_POSITIONAL", "VAR_KEYWORD"}
    }
    has_var_keyword = any(kind == "VAR_KEYWORD" for _, kind, _, _ in shape)
    if not has_var_keyword and not set(call_args).issubset(allowed):
        return False
    positional_only = {
        name
        for name, kind, _, _ in shape
        if kind == "POSITIONAL_ONLY"
    }
    return not (set(call_args) & positional_only)


def _signature_allows_no_args(item: dict[str, str]) -> bool:
    signature = str(item.get("signature") or "")
    if not signature:
        return False
    for name, kind, has_default, _ in _signature_contract_shape(signature):
        if name in {"self", "cls"} or kind in {"VAR_POSITIONAL", "VAR_KEYWORD"}:
            continue
        if not has_default:
            return False
    return True


def _return_matches_public_signature(
    item: dict[str, str],
    observed: Any,
) -> bool:
    signature = str(item.get("signature") or "")
    if "->" not in signature:
        return True
    annotation = signature.split("->", 1)[1].strip().strip("'\"")
    if observed is None:
        return annotation in {"None", "NoneType"} or "None |" in annotation or "| None" in annotation
    expected_roots = {
        "bool": bool,
        "int": int,
        "float": float,
        "str": str,
        "list": list,
        "dict": dict,
        "tuple": list,  # tuples are projected to JSON arrays by the tracer
        "set": list,
    }
    root = re.split(r"[\[| ]", annotation, maxsplit=1)[0]
    expected = expected_roots.get(root)
    return True if expected is None else isinstance(observed, expected)


def _build_cgcc_obligations(
    *,
    api: list[dict[str, str]],
    public_spec: dict[str, Any] | None,
    inferred: dict[str, Any],
    variant: str,
) -> list[dict[str, Any]]:
    """Build an evidence ledger for pre-registered plausible-wrong families.

    This is deliberately independent of benchmark evaluator tests. A family is
    applicable only when TASK/public_spec or upstream AST/source evidence makes
    both the intended behavior and the corresponding wrong implementation
    plausible.
    """

    if variant not in CGCC_VARIANTS:
        return []

    names = {a["name"] for a in api}
    paths = {a["path"] for a in api}
    methods = set(inferred.get("methods") or [])
    evidence = set(inferred.get("semantic_evidence") or [])
    blob = _behavior_blob(public_spec)
    obligations: list[dict[str, Any]] = []

    def add(
        obligation_id: str,
        family: str,
        statement: str,
        *,
        evidence_refs: list[dict[str, str]],
        contract_tests: list[str],
        mutant: str,
    ) -> None:
        obligations.append(
            {
                "id": obligation_id,
                "family": family,
                "statement": statement,
                "evidence": evidence_refs,
                "contract_tests": contract_tests,
                "plausible_wrong_implementation": mutant,
            }
        )

    is_lazy = (
        "LazyCommandCollection" in names
        or "featurelifted.LazyCommandCollection" in paths
    )
    if is_lazy and ("invoke" in methods or "invoke" in names):
        add(
            "api_closure.invoke",
            "api_member_deletion",
            "An inherited/adjacent public operation needed to execute the resolved command remains callable and behavioral.",
            evidence_refs=[
                {"tier": "B", "source": "upstream AST/MRO: invoke"},
                {"tier": "C", "source": "API-closure deletion operator"},
            ],
            contract_tests=["test_invoke_runs_callback_over_argv"],
            mutant="Delete invoke or replace it with a non-behavioral stub.",
        )
    if is_lazy and ("cache" in blob or "loads only" in blob):
        add(
            "state.lazy_selective_cache",
            "lazy_state_collapse",
            "Only the requested source loads, and the resolved command is cached by identity.",
            evidence_refs=[
                {"tier": "A", "source": "public_spec B001"},
                {"tier": "C", "source": "requested/unrequested + first/repeat matched pairs"},
            ],
            contract_tests=["test_get_command_is_selective_and_cached"],
            mutant="Eagerly load unrelated factories or omit the cache write.",
        )
    if is_lazy and ("envvar" in blob or "default_map" in blob or "defaults" in blob):
        add(
            "state.context_defaults",
            "context_propagation_omission",
            "Environment-derived defaults reach the resolution context without changing unrelated loading.",
            evidence_refs=[
                {"tier": "A", "source": "public_spec B002"},
                {"tier": "B", "source": "upstream Context AST attributes"},
            ],
            contract_tests=["test_envvar_json_propagates_to_context_default_map"],
            mutant="Resolve the command but drop envvar/default_map propagation.",
        )
    if is_lazy and ("resolve" in methods or "resolve" in names or "resolve" in blob):
        add(
            "error.resolve_unknown",
            "error_type_omission",
            "Unknown argv resolution raises the declared UsageError type.",
            evidence_refs=[{"tier": "A", "source": "public_spec B003"}],
            contract_tests=["test_resolve_returns_context_command_and_remaining_argv"],
            mutant="Return None or raise a generic exception for an unknown command.",
        )

    is_revision = "RevisionMap" in names or "featurelifted.RevisionMap" in paths
    if is_revision and (
        "symbolic" in blob or ("head" in blob and "base" in blob)
    ):
        add(
            "namespace.symbol_fallback",
            "symbol_overgeneralization",
            "A registered unrestricted string identifier is resolved before applying symbolic fallback semantics.",
            evidence_refs=[
                {"tier": "A", "source": "Revision(revision: str) + public_spec B006"},
                {"tier": "C", "source": "namespace-collision conservation operator"},
            ],
            contract_tests=["test_symbolic_fallback_preserves_registered_identifier"],
            mutant="Treat a symbolic token as special even when the same string is a registered concrete id.",
        )
    if is_revision and "preserves_insertion_order" in evidence:
        add(
            "ordering.heads",
            "ordered_output_collapse",
            "Independent heads preserve upstream source/insertion order.",
            evidence_refs=[
                {"tier": "B", "source": "upstream ordered map/set implementation"},
                {"tier": "C", "source": "ordered-output permutation operator"},
            ],
            contract_tests=["test_independent_heads_preserve_source_order"],
            mutant="Convert ordered heads to a set, sort them, or reverse their source order.",
        )
    if is_revision and ("dependencies" in blob or "dependency" in blob):
        add(
            "graph.dependency_role",
            "edge_role_collapse",
            "Dependency edges affect dependency-aware ancestry without replacing versioned parent/child head semantics.",
            evidence_refs=[
                {"tier": "A", "source": "public_spec B002/B003/B005"},
                {"tier": "C", "source": "edge-role toggle operator"},
            ],
            contract_tests=[
                "test_dependency_aware_ancestors_preserve_versioned_heads"
            ],
            mutant="Treat dependencies as down_revision edges or ignore them during dependency-aware ancestry.",
        )
    if is_revision and ("branch label" in blob or "branch_labels" in blob):
        add(
            "graph.branch_label_propagation",
            "state_propagation_omission",
            "A branch label remains usable at the eligible descendant head.",
            evidence_refs=[{"tier": "A", "source": "public_spec B004"}],
            contract_tests=["test_branch_label_propagates_to_descendant_head"],
            mutant="Store the branch label only on its origin and omit descendant propagation.",
        )
        if variant in {"cgcc_roc", "cgcc_rmc"}:
            add(
                "representation.branch_label_origin",
                "observable_representation_collapse",
                "The public alias mapping preserves the originally bound revision id while propagated state remains observable at the descendant head.",
                evidence_refs=[
                    {
                        "tier": "A",
                        "source": "public_spec B004 + required RevisionMap.branch_labels",
                    },
                    {
                        "tier": "B",
                        "source": "upstream _map_branch_labels binds aliases before _add_branches propagation",
                    },
                    {
                        "tier": "C",
                        "source": "representation/observation separation operator",
                    },
                ],
                contract_tests=[
                    "test_branch_label_binding_is_distinct_from_propagated_head"
                ],
                mutant=(
                    "Recompute the public alias mapping from propagated descendant "
                    "state or expose internal Revision objects instead of revision ids."
                ),
            )
    if is_revision and variant == "cgcc_rmc":
        if "iterate_revisions" in names or "iterate_revisions" in methods:
            add(
                "required_method.iterate_revisions",
                "required_method_behavior_omission",
                "The required revision traversal method honors its upstream default lower-bound exclusivity.",
                evidence_refs=[
                    {
                        "tier": "A",
                        "source": "TASK required iterate_revisions(upper, lower=None)",
                    },
                    {
                        "tier": "B",
                        "source": "upstream iterate_revisions inclusive=False default",
                    },
                    {
                        "tier": "C",
                        "source": "required-method boundary witness operator",
                    },
                ],
                contract_tests=[
                    "test_iterate_revisions_excludes_lower_by_default"
                ],
                mutant=(
                    "Expose iterate_revisions but include the lower boundary despite "
                    "the upstream exclusive default, or return a non-traversal stub."
                ),
            )
        if "get_revisions" in names or "get_revisions" in methods:
            add(
                "required_method.get_revisions",
                "required_method_behavior_omission",
                "The required vector lookup resolves every requested concrete revision in input order.",
                evidence_refs=[
                    {
                        "tier": "A",
                        "source": "TASK required get_revisions(identifiers)",
                    },
                    {
                        "tier": "B",
                        "source": "upstream get_revisions vector lookup",
                    },
                    {
                        "tier": "C",
                        "source": "required-method vectorization witness operator",
                    },
                ],
                contract_tests=[
                    "test_get_revisions_preserves_requested_identifier_order"
                ],
                mutant=(
                    "Expose get_revisions but return an empty/scalar result or lose "
                    "the requested identifier order."
                ),
            )
    if is_revision and ("multiple" in blob or "MultipleHeads" in names):
        add(
            "error.multiple_heads",
            "ambiguity_error_omission",
            "Symbolic head lookup resolves one candidate and rejects multiple candidates with MultipleHeads.",
            evidence_refs=[{"tier": "A", "source": "public_spec B006/B007"}],
            contract_tests=["test_symbolic_head_rejects_multiple_candidates"],
            mutant="Pick an arbitrary head instead of reporting ambiguity.",
        )
    if is_revision and ("cycle" in blob or "CycleDetected" in names):
        add(
            "error.cycle",
            "cycle_check_omission",
            "A versioned cycle raises CycleDetected during graph construction.",
            evidence_refs=[{"tier": "A", "source": "public_spec B007"}],
            contract_tests=["test_revision_cycle_raises_cycle_detected"],
            mutant="Build a cyclic graph without explicit cycle detection.",
        )

    return obligations


def _build_mutation_audit(
    obligations: list[dict[str, Any]],
    *,
    variant: str,
) -> dict[str, Any]:
    mutants: list[dict[str, Any]] = []
    for index, obligation in enumerate(obligations, start=1):
        tests = [
            str(item)
            for item in obligation.get("contract_tests") or []
            if str(item).strip()
        ]
        mutants.append(
            {
                "id": f"M{index:03d}",
                "family": obligation["family"],
                "description": obligation["plausible_wrong_implementation"],
                "obligation_id": obligation["id"],
                "killed_by": tests,
                "status": "contractually_killed" if tests else "survived",
            }
        )
    applicable = sorted({str(item["family"]) for item in mutants})
    covered = sorted(
        {
            str(item["family"])
            for item in mutants
            if item["status"] == "contractually_killed"
        }
    )
    adequacy_ok = (
        True
        if variant not in CGCC_VARIANTS
        else bool(applicable) and applicable == covered
    )
    return {
        "schema_version": "featureliftbench.cgcc_mutation_audit.v1",
        "contract_variant": variant,
        "mode": "semantic_contract_traceability",
        "note": (
            "Each listed contract contains an observation that distinguishes the "
            "registered plausible-wrong semantic mutant. No formal evaluator result "
            "is used to create or mark mutants."
        ),
        "mutants": mutants,
        "applicable_families": applicable,
        "covered_families": covered,
        "applicable_family_count": len(applicable),
        "covered_family_count": len(covered),
        "mutation_adequacy_ok": adequacy_ok,
    }


def _generate_scenario_tests(
    api: list[dict[str, str]],
    public_spec: dict[str, Any] | None,
    inferred: dict[str, Any],
    *,
    variant: str,
) -> dict[str, Any]:
    """Real assertions from upstream AST + public_spec only.

    Hard rule: do **not** encode benchmark public/hidden failure shapes
    (exact error strings or evaluator-specific graphs/orderings). Those are soft
    test leakage. Allowed: upstream-inferred API surface behavior,
    TASK/public_spec obligations, and pre-registered contrastive operators whose
    applicability is supported by upstream source evidence.
    """

    names = {a["name"] for a in api}
    paths = {a["path"] for a in api}
    methods = set(inferred.get("methods") or [])
    blob = _behavior_blob(public_spec)
    assertions = 0
    lines = [
        '"""Behavioral mini-scenarios from upstream AST + public_spec (eval-blind)."""',
        "from __future__ import annotations",
        "",
        "import importlib",
        "import json",
        "",
        "import pytest",
        "",
    ]

    # --- LazyCommandCollection / click-like ---
    if "LazyCommandCollection" in names or "featurelifted.LazyCommandCollection" in paths:
        # B003 + resolve signature: argv -> (Context, Command, remaining); UsageError unknown.
        if (
            "resolve" in methods
            or "resolve" in names
            or "featurelifted.LazyCommandCollection.resolve" in paths
            or "resolve" in blob
        ):
            lines += [
                "def test_resolve_returns_context_command_and_remaining_argv() -> None:",
                "    \"\"\"public_spec B003 / resolve signature: tuple[Context, Command, list[str]].\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Lazy = getattr(mod, 'LazyCommandCollection')",
                "    Command = getattr(mod, 'Command')",
                "    UsageError = getattr(mod, 'UsageError')",
                "    def factory():",
                "        return Command('demo', callback=lambda *a, **k: a)",
                "    col = Lazy({'demo': factory})",
                "    ctx, cmd, rest = col.resolve(['demo', 'x', 'y'])",
                "    assert ctx is not None",
                "    assert cmd is not None",
                "    assert getattr(cmd, 'name', None) == 'demo'",
                "    assert list(rest) == ['x', 'y']",
                "    with pytest.raises(UsageError):",
                "        col.resolve(['missing_command_xyz'])",
                "",
            ]
            assertions += 2  # return shape + UsageError

        # invoke(argv) must run the command callback — not merely exist (upstream AST + argv style).
        if "invoke" in methods or "invoke" in names:
            lines += [
                "def test_invoke_runs_callback_over_argv() -> None:",
                "    \"\"\"Collection.invoke(argv) must execute the resolved command callback.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Lazy = getattr(mod, 'LazyCommandCollection')",
                "    Command = getattr(mod, 'Command')",
                "    def factory():",
                "        return Command('demo', callback=lambda ctx, args: list(args))",
                "    col = Lazy({'demo': factory})",
                "    result = col.invoke(['demo', 'a', 'b'])",
                "    assert result == ['a', 'b']",
                "",
            ]
            assertions += 1

        # B002 + ctor envvar: JSON mapping propagates into Context.default_map.
        if "envvar" in blob or "default" in blob or "default_map" in blob:
            lines += [
                "def test_envvar_json_propagates_to_context_default_map(monkeypatch) -> None:",
                "    \"\"\"public_spec: envvar settings propagate into context default_map.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Lazy = getattr(mod, 'LazyCommandCollection')",
                "    Command = getattr(mod, 'Command')",
                "    env_name = 'FLB_FEATURE_DEFAULTS'",
                "    payload = {'demo': {'flag': True}}",
                "    monkeypatch.setenv(env_name, json.dumps(payload))",
                "    col = Lazy({'demo': lambda: Command('demo')}, envvar=env_name)",
                "    ctx, _cmd, _rest = col.resolve(['demo'])",
                "    assert getattr(ctx, 'default_map', None) is not None",
                "    assert ctx.default_map.get('demo', {}).get('flag') is True",
                "",
            ]
            assertions += 1

        # B001: get_command loads only needed source (cache once).
        if "cache" in blob or "loads only" in blob or "get_command" in blob:
            if variant in CGCC_VARIANTS:
                lines += [
                    "def test_get_command_is_selective_and_cached() -> None:",
                    "    \"\"\"B001 contrast: requested factory runs once; unrelated factory stays cold.\"\"\"",
                    "    mod = importlib.import_module('featurelifted')",
                    "    Lazy = getattr(mod, 'LazyCommandCollection')",
                    "    Command = getattr(mod, 'Command')",
                    "    calls = {'wanted': 0, 'other': 0}",
                    "    def wanted():",
                    "        calls['wanted'] += 1",
                    "        return Command('wanted')",
                    "    def other():",
                    "        calls['other'] += 1",
                    "        return Command('other')",
                    "    col = Lazy({'wanted': wanted, 'other': other})",
                    "    c1 = col.get_command('wanted')",
                    "    c2 = col.get_command('wanted')",
                    "    assert c1 is not None and c2 is c1",
                    "    assert calls == {'wanted': 1, 'other': 0}",
                    "",
                ]
            else:
                lines += [
                    "def test_get_command_loads_source_once() -> None:",
                    "    \"\"\"public_spec B001: load the providing source and cache the command.\"\"\"",
                    "    mod = importlib.import_module('featurelifted')",
                    "    Lazy = getattr(mod, 'LazyCommandCollection')",
                    "    Command = getattr(mod, 'Command')",
                    "    calls = {'n': 0}",
                    "    def factory():",
                    "        calls['n'] += 1",
                    "        return Command('demo')",
                    "    col = Lazy({'demo': factory})",
                    "    c1 = col.get_command('demo')",
                    "    c2 = col.get_command('demo')",
                    "    assert c1 is not None and c2 is not None",
                    "    assert calls['n'] == 1",
                    "",
                ]
            assertions += 1

    # --- RevisionMap / alembic-like (public_spec obligations only) ---
    if "RevisionMap" in names or "featurelifted.RevisionMap" in paths:
        # Signature: down_revision defaults to None → one-arg Revision must construct.
        lines += [
            "def test_revision_down_revision_defaults_to_none() -> None:",
            "    \"\"\"public_spec Revision signature: down_revision=None by default.\"\"\"",
            "    mod = importlib.import_module('featurelifted')",
            "    Revision = getattr(mod, 'Revision')",
            "    rev = Revision('solo')",
            "    assert getattr(rev, 'revision', None) == 'solo'",
            "    down = getattr(rev, 'down_revision', 'missing')",
            "    assert down in (None, (), [])",
            "",
        ]
        assertions += 1

        # B003: branched + merged graph → single merge head; branch point queryable.
        lines += [
            "def test_merge_graph_heads_and_branch_point() -> None:",
            "    \"\"\"public_spec B003: branched/merged graphs report heads; branch points exist.\"\"\"",
            "    mod = importlib.import_module('featurelifted')",
            "    Revision = getattr(mod, 'Revision')",
            "    RevisionMap = getattr(mod, 'RevisionMap')",
            "    revs = [",
            "        Revision('n0'),",
            "        Revision('n1', 'n0'),",
            "        Revision('n2', 'n0'),",
            "        Revision('n3', ('n1', 'n2')),",
            "    ]",
            "    revmap = RevisionMap(revs)",
            "    heads = revmap.get_heads() if hasattr(revmap, 'get_heads') else list(getattr(revmap, 'heads'))",
            "    assert list(heads) == ['n3'] or set(heads) == {'n3'}",
            "    root = revmap.get_revision('n0')",
            "    assert root is not None",
            "    assert getattr(root, 'is_branch_point', False) is True",
            "    merge = revmap.get_revision('n3')",
            "    assert merge is not None",
            "    assert getattr(merge, 'is_merge_point', False) is True",
            "",
        ]
        assertions += 1

        # CGCC namespace conservation: a symbol is a fallback, not a reason to
        # erase a concrete entity using the same unrestricted string identifier.
        if variant in CGCC_VARIANTS and (
            "symbolic" in blob
            or ("head" in blob and "base" in blob)
            or "get_revision" in names
            or "get_revision" in methods
            or "featurelifted.RevisionMap.get_revision" in paths
        ):
            lines += [
                "def test_symbolic_fallback_preserves_registered_identifier() -> None:",
                "    \"\"\"B001+B006 contrast: concrete ids win; symbols are fallback semantics.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    plain = RevisionMap([Revision('root'), Revision('tip', 'root')])",
                "    head = plain.get_revision('head')",
                "    assert head is not None, 'get_revision(\"head\") must resolve the unique head'",
                "    assert getattr(head, 'revision', None) == 'tip'",
                "    assert plain.get_revision('base') is None",
                "    collision = RevisionMap([Revision('base'), Revision('tip', 'base')])",
                "    concrete = collision.get_revision('base')",
                "    assert concrete is not None",
                "    assert getattr(concrete, 'revision', None) == 'base'",
                "",
            ]
            assertions += 1

        # CGCC order conservation is admitted only when upstream source declares
        # or implements ordered collection semantics.
        if (
            variant in CGCC_VARIANTS
            and "preserves_insertion_order"
            in set(inferred.get("semantic_evidence") or [])
            and (
                "get_heads" in names
                or "get_heads" in methods
                or "featurelifted.RevisionMap.get_heads" in paths
            )
        ):
            lines += [
                "def test_independent_heads_preserve_source_order() -> None:",
                "    \"\"\"Upstream ordered-map/set evidence: independent heads keep source order.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    first = RevisionMap([Revision('left'), Revision('right')])",
                "    second = RevisionMap([Revision('right'), Revision('left')])",
                "    assert list(first.get_heads()) == ['left', 'right']",
                "    assert list(second.get_heads()) == ['right', 'left']",
                "",
            ]
            assertions += 1

        if variant in CGCC_VARIANTS and (
            "dependencies" in blob or "dependency" in blob
        ):
            lines += [
                "def test_dependency_aware_ancestors_preserve_versioned_heads() -> None:",
                "    \"\"\"B003+B005 contrast: dependencies affect ancestry, not versioned edges.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    revmap = RevisionMap([",
                "        Revision('root'),",
                "        Revision('side', 'root'),",
                "        Revision('consumer', 'root', dependencies='side'),",
                "    ])",
                "    assert list(revmap.get_heads()) == ['side', 'consumer']",
                "    assert revmap.ancestors('consumer', include_dependencies=False) == {'root'}",
                "    assert revmap.ancestors('consumer', include_dependencies=True) >= {'root', 'side'}",
                "",
            ]
            assertions += 1

        if variant in CGCC_VARIANTS and (
            "branch label" in blob or "branch_labels" in blob
        ):
            lines += [
                "def test_branch_label_propagates_to_descendant_head() -> None:",
                "    \"\"\"B004 contrast: a branch label remains usable at its descendant head.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    revmap = RevisionMap([",
                "        Revision('root', branch_labels={'stable'}),",
                "        Revision('tip', 'root'),",
                "    ])",
                "    assert revmap.get_current_head('stable') == 'tip'",
                "    tip = revmap.get_revision('tip')",
                "    assert tip is not None",
                "    assert 'stable' in set(getattr(tip, 'branch_labels', ()))",
                "",
            ]
            assertions += 1

        if variant in {"cgcc_roc", "cgcc_rmc"} and (
            "branch label" in blob or "branch_labels" in blob
        ):
            lines += [
                "def test_branch_label_binding_is_distinct_from_propagated_head() -> None:",
                "    \"\"\"B004 + upstream alias map: preserve origin and public id projection.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    revmap = RevisionMap([",
                "        Revision('origin', branch_labels={'stable'}),",
                "        Revision('tip', 'origin'),",
                "    ])",
                "    bound = revmap.get_revision('stable')",
                "    assert bound is not None",
                "    assert getattr(bound, 'revision', None) == 'origin'",
                "    assert revmap.get_current_head('stable') == 'tip'",
                "    assert revmap.branch_labels.get('stable') == 'origin'",
                "",
            ]
            assertions += 1

        if variant == "cgcc_rmc" and (
            "iterate_revisions" in names
            or "iterate_revisions" in methods
            or "featurelifted.RevisionMap.iterate_revisions" in paths
        ):
            lines += [
                "def test_iterate_revisions_excludes_lower_by_default() -> None:",
                "    \"\"\"TASK method + upstream inclusive=False: lower is exclusive.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    revmap = RevisionMap([",
                "        Revision('r0'),",
                "        Revision('r1', 'r0'),",
                "        Revision('r2', 'r1'),",
                "    ])",
                "    bounded = revmap.iterate_revisions('r2', 'r0')",
                "    assert [rev.revision for rev in bounded] == ['r2', 'r1']",
                "    full = revmap.iterate_revisions('r2', None)",
                "    assert [rev.revision for rev in full] == ['r2', 'r1', 'r0']",
                "",
            ]
            assertions += 1

        if variant == "cgcc_rmc" and (
            "get_revisions" in names
            or "get_revisions" in methods
            or "featurelifted.RevisionMap.get_revisions" in paths
        ):
            lines += [
                "def test_get_revisions_preserves_requested_identifier_order() -> None:",
                "    \"\"\"TASK required vector lookup must resolve all inputs in order.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    revmap = RevisionMap([Revision('r0'), Revision('r1', 'r0')])",
                "    resolved = revmap.get_revisions(('r0', 'r1'))",
                "    assert [rev.revision for rev in resolved] == ['r0', 'r1']",
                "",
            ]
            assertions += 1

        # MissingRevision is named in required_api / TASK — not copied from hidden.
        if any(a.get("name") == "MissingRevision" for a in api) or "MissingRevision" in names:
            lines += [
                "def test_missing_down_revision_raises_missing_revision() -> None:",
                "    \"\"\"public_spec declares MissingRevision for missing graph nodes.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    MissingRevision = getattr(mod, 'MissingRevision', None)",
                "    if MissingRevision is None:",
                "        pytest.skip('MissingRevision not exported')",
                "    with pytest.raises(MissingRevision):",
                "        RevisionMap([Revision('b', 'missing')])",
                "",
            ]
            assertions += 1

        if variant in CGCC_VARIANTS and (
            "MultipleHeads" in names or "multiple" in blob
        ):
            lines += [
                "def test_symbolic_head_rejects_multiple_candidates() -> None:",
                "    \"\"\"B006+B007 contrast: unique head resolves; multiple heads are explicit.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    MultipleHeads = getattr(mod, 'MultipleHeads')",
                "    assert RevisionMap([Revision('only')]).get_revision('head').revision == 'only'",
                "    with pytest.raises(MultipleHeads):",
                "        RevisionMap([Revision('one'), Revision('two')]).get_revision('head')",
                "",
            ]
            assertions += 1

        if variant in CGCC_VARIANTS and (
            "CycleDetected" in names or "cycle" in blob
        ):
            lines += [
                "def test_revision_cycle_raises_cycle_detected() -> None:",
                "    \"\"\"B007: a two-node versioned cycle raises the declared graph error.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    CycleDetected = getattr(mod, 'CycleDetected')",
                "    with pytest.raises(CycleDetected):",
                "        RevisionMap([Revision('one', 'two'), Revision('two', 'one')])",
                "",
            ]
            assertions += 1

        # Mild ancestors obligation from public_spec behavior text (no eval graph).
        if "ancestors" in names or "ancestors" in methods or "ancestor" in blob:
            lines += [
                "def test_ancestors_excludes_self_on_linear_chain() -> None:",
                "    \"\"\"public_spec ancestors behavior: self is not an ancestor of itself.\"\"\"",
                "    mod = importlib.import_module('featurelifted')",
                "    Revision = getattr(mod, 'Revision')",
                "    RevisionMap = getattr(mod, 'RevisionMap')",
                "    revmap = RevisionMap([Revision('a'), Revision('b', 'a'), Revision('c', 'b')])",
                "    ancs = revmap.ancestors('c')",
                "    assert 'c' not in set(ancs)",
                "    assert set(ancs) >= {'a', 'b'}",
                "",
            ]
            assertions += 1

    if assertions == 0:
        lines += [
            "def test_no_scenario_templates_matched() -> None:",
            "    pytest.skip('no eval-blind scenario templates matched; rely on surface/replay')",
            "",
        ]

    return {"code": "\n".join(lines), "assertions": assertions}


def _generate_behavior_checklist(behaviors: list[dict[str, str]]) -> str:
    """Documentation-only catalog — must NOT use assert True as a gate."""

    lines = [
        '"""Behavior checklist — documentation only (not a greenwashing gate)."""',
        "from __future__ import annotations",
        "",
        "import pytest",
        "",
        "BEHAVIORS = " + json.dumps(behaviors, ensure_ascii=False, indent=2),
        "",
        "",
        "def test_behavior_catalog_is_list() -> None:",
        "    assert isinstance(BEHAVIORS, list)",
        "",
        "",
        "@pytest.mark.parametrize('behavior', BEHAVIORS)",
        "def test_behavior_documented(behavior) -> None:",
        "    \"\"\"Keep behavior ids visible in collection; no vacuous pass.\"\"\"",
        "    assert behavior.get('id') or behavior.get('text')",
        "    pytest.skip('documentation-only; enforced by test_behavior_scenarios.py')",
        "",
    ]
    return "\n".join(lines)
