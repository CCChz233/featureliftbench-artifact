"""Budgeted Operational Support Subgraph constructor (Design v2 MVP)."""

from __future__ import annotations

import json
from typing import Any, Iterable

from .models import GraphNode
from .query import GraphQueryEngine


# Frozen default weights for path utility (pre-register before agent pilots).
DEFAULT_WEIGHTS = {
    "relevance": 1.0,
    "coverage": 1.6,
    "evidence": 1.0,
    "distance": 0.35,
    "noise": 1.0,
    "cost": 0.002,
}

HIGH_PRIORITY_KINDS = frozenset(
    {
        "DEFINES",
        "EXPORTS",
        "PROVIDES_MEMBER",
        "RETURNS_TYPE",
        "RAISES",
        "LOADS_RESOURCE",
        "PACKAGED_BY",
        "READS_ENV",
        "READS_CONFIG",
        "READS_CWD",
        "DEFAULT_DEFINED_BY",
        "REGISTERS",
        "RESOLVES_VIA",
        "INHERITS",
    }
)

NOISE_PATH_MARKERS = (
    "logging",
    "cli",
    "argparse",
    "click",
    "unittest",
    "pytest",
    "docs/",
    "test_",
    "/tests/",
)

CATEGORY_BY_KIND = {
    "DEFINES": "implementation",
    "CALLS": "implementation",
    "INHERITS": "data",
    "EXPORTS": "interface",
    "PROVIDES_MEMBER": "interface",
    "RETURNS_TYPE": "interface",
    "RAISES": "interface",
    "LOADS_RESOURCE": "resource",
    "PACKAGED_BY": "resource",
    "READS_ENV": "configuration",
    "READS_CONFIG": "configuration",
    "READS_CWD": "configuration",
    "DEFAULT_DEFINED_BY": "configuration",
    "REGISTERS": "dispatch",
    "RESOLVES_VIA": "dispatch",
    "DYNAMIC_IMPORT": "dispatch",
    "MODULE_STATE": "state",
    "MUTABLE_GLOBAL": "state",
}


def build_operational_support(
    engine: GraphQueryEngine,
    seeds: Iterable[str],
    *,
    budget_tokens: int = 8_000,
    max_depth: int = 4,
    max_nodes: int = 80,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Return Core / Support / Boundaries under a token budget.

    This is a retrieval view, not an agent obligation ledger and not a proven
    executable minimal closure.
    """

    seed_list = [str(item).strip() for item in seeds if str(item).strip()]
    if not seed_list:
        raise ValueError("at least one --seed is required")
    if budget_tokens < 256:
        raise ValueError("budget_tokens must be at least 256")

    resolved_seeds, ambiguous = _resolve_seeds(engine, seed_list)
    if not resolved_seeds and ambiguous:
        return {
            "schema_version": "featureliftbench.repo_graph.support.v1",
            "seeds": seed_list,
            "ambiguous_seeds": ambiguous,
            "core": [],
            "support": [],
            "boundaries": [],
            "budget": {"limit_tokens": budget_tokens, "used_tokens": 0},
            "status": "ambiguous_seeds",
        }
    if not resolved_seeds:
        raise ValueError(f"could not resolve seeds: {seed_list}")

    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    closure = engine.closure(
        [node.stable_id for node in resolved_seeds],
        max_nodes=max_nodes,
        include_candidates=False,
    )
    root_ids = {node.id for node in resolved_seeds}
    nodes_by_id = {node.id: node for node in engine.snapshot.nodes}

    candidates: list[dict[str, Any]] = []
    covered_categories: set[str] = set()
    for node_payload in closure.get("nodes", []):
        node = engine.index.resolve_node(node_payload["stable_id"])
        if node is None or node.id in root_ids:
            continue
        path_info = _best_path(engine, resolved_seeds[0], node, max_depth=max_depth)
        if path_info is None:
            continue
        utility = _score_path(
            path_info,
            covered_categories=covered_categories,
            weights=w,
            seed=resolved_seeds[0],
        )
        category = path_info["category"]
        candidates.append(
            {
                "entity": node.stable_id,
                "role": _role_for_category(category),
                "category": category,
                "evidence_path": path_info["entity_path"],
                "utility": utility,
                "cost_tokens": path_info["cost_tokens"],
                "node": node,
            }
        )

    candidates.sort(key=lambda item: (-item["utility"], item["entity"]))
    selected: list[dict[str, Any]] = []
    used_tokens = _estimate_tokens(
        {
            "seeds": [node.stable_id for node in resolved_seeds],
            "core": [],
            "support": [],
            "boundaries": [],
        }
    )
    for item in candidates:
        next_cost = int(item["cost_tokens"])
        if used_tokens + next_cost > budget_tokens and selected:
            break
        if used_tokens + next_cost > budget_tokens and not selected and next_cost > budget_tokens:
            continue
        selected.append(item)
        covered_categories.add(str(item["category"]))
        used_tokens += next_cost

    core = [
        {
            "entity": node.stable_id,
            "role": "seed",
            "evidence_path": [node.stable_id],
        }
        for node in resolved_seeds
    ]
    for edge in engine.snapshot.edges:
        if edge.source not in root_ids or edge.target is None:
            continue
        if edge.kind not in {
            "DEFINES",
            "CALLS",
            "EXPORTS",
            "PROVIDES_MEMBER",
            "RETURNS_TYPE",
            "RAISES",
            "LOADS_RESOURCE",
            "READS_CONFIG",
            "READS_ENV",
            "REGISTERS",
        } or edge.resolution not in {"exact", "probable", "candidate"}:
            continue
        target = nodes_by_id.get(edge.target)
        if target is None:
            continue
        if any(item["entity"] == target.stable_id for item in core):
            continue
        core.append(
            {
                "entity": target.stable_id,
                "role": "direct_implementation"
                if edge.kind in {"DEFINES", "CALLS"}
                else _role_for_category(CATEGORY_BY_KIND.get(edge.kind, "implementation")),
                "evidence_path": [resolved_seeds[0].stable_id, target.stable_id],
                "via": edge.kind,
            }
        )

    core_ids = {item["entity"] for item in core}
    support = [
        {
            "entity": item["entity"],
            "role": item["role"],
            "category": item["category"],
            "evidence_path": item["evidence_path"],
            "utility": round(float(item["utility"]), 4),
        }
        for item in selected
        if item["entity"] not in core_ids
    ]

    boundaries = _boundaries_from_closure(engine, closure, root_ids, nodes_by_id)
    guidance = _build_guidance(engine, core=core, support=support, boundaries=boundaries)
    result = {
        "schema_version": "featureliftbench.repo_graph.support.v1",
        "seeds": [node.stable_id for node in resolved_seeds],
        "ambiguous_seeds": ambiguous,
        "core": core,
        "support": support,
        "boundaries": boundaries,
        "guidance": guidance,
        "covered_categories": sorted(covered_categories),
        "budget": {
            "limit_tokens": budget_tokens,
            "used_tokens": _estimate_tokens(
                {
                    "core": core,
                    "support": support,
                    "boundaries": boundaries,
                    "guidance": guidance,
                }
            ),
            "selection_used_tokens": used_tokens,
        },
        "status": "ok",
        "truncated": bool(closure.get("truncated")),
    }
    while support and result["budget"]["used_tokens"] > budget_tokens:
        support.pop()
        result["support"] = support
        result["guidance"] = _build_guidance(
            engine, core=core, support=support, boundaries=boundaries
        )
        result["budget"]["used_tokens"] = _estimate_tokens(
            {
                "core": core,
                "support": support,
                "boundaries": boundaries,
                "guidance": result["guidance"],
            }
        )
    return result


def render_compact_guidance(support_result: dict[str, Any]) -> str:
    """Human-actionable markdown for bootstrap injection (token-efficient)."""

    guidance = support_result.get("guidance") if isinstance(support_result.get("guidance"), dict) else {}
    lines = [
        "### RSG start-here (advisory)",
        "",
        "Read these paths **before** broad repository search. Prefer copying from them.",
        "",
    ]
    files = guidance.get("start_here_files") or []
    if files:
        lines.append("**Files**")
        for item in files[:12]:
            symbols = ", ".join(item.get("symbols") or [])
            suffix = f" — {symbols}" if symbols else ""
            lines.append(f"- `{item.get('path')}`{suffix}")
        lines.append("")
    watch = guidance.get("watch") or []
    if watch:
        lines.append("**Watch / likely missing deps**")
        for item in watch[:8]:
            lines.append(f"- {item}")
        lines.append("")
    seeds = support_result.get("seeds") or []
    if seeds:
        seed = seeds[0]
        lines.append(
            "If public tests fail on missing API/config/resource/dispatch, run:\n"
            f"`flb-rsg support --seed {seed} --budget-tokens 4000`"
        )
        lines.append("")
    return "\n".join(lines)


def _build_guidance(
    engine: GraphQueryEngine,
    *,
    core: list[dict[str, Any]],
    support: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
) -> dict[str, Any]:
    ranked_entities = [item["entity"] for item in core] + [item["entity"] for item in support]
    file_map: dict[str, list[str]] = {}
    for entity in ranked_entities:
        node = engine.index.resolve_node(entity)
        if node is None or node.span is None:
            continue
        path = node.span.path
        symbol = node.qualified_name or node.name
        bucket = file_map.setdefault(path, [])
        if symbol not in bucket:
            bucket.append(symbol)
    start_here_files = [
        {"path": path, "symbols": symbols[:6]}
        for path, symbols in list(file_map.items())[:12]
    ]
    watch: list[str] = []
    for item in boundaries[:8]:
        kind = item.get("kind") or "boundary"
        source = item.get("source") or "?"
        reason = item.get("reason") or ""
        watch.append(f"`{source}` [{kind}] {reason}".strip())
    return {
        "start_here_files": start_here_files,
        "watch": watch,
        "strategy": "read_start_here_first",
    }


_SEED_KIND_PRIORITY = {
    "function": 0,
    "method": 1,
    "class": 2,
    "type": 3,
    "module": 8,
    "file": 9,
    "dependency": 10,
    "repository": 11,
}


def _resolve_seeds(
    engine: GraphQueryEngine, seeds: list[str]
) -> tuple[list[GraphNode], list[dict[str, Any]]]:
    resolved: list[GraphNode] = []
    ambiguous: list[dict[str, Any]] = []
    for seed in seeds:
        direct = engine.index.resolve_node(seed)
        if direct is not None:
            resolved.append(direct)
            continue
        matches = engine.search(seed, limit=12).get("matches", [])
        if not matches:
            ambiguous.append({"seed": seed, "candidates": [], "reason": "unresolved"})
            continue
        ranked = sorted(
            matches,
            key=lambda item: (
                -int(item.get("score") or 0),
                _SEED_KIND_PRIORITY.get(str(item.get("kind") or ""), 5),
                str(item.get("stable_id") or ""),
            ),
        )
        top = ranked[0]
        top_score = int(top.get("score") or 0)
        contenders = [
            item
            for item in ranked
            if int(item.get("score") or 0) == top_score
            and _SEED_KIND_PRIORITY.get(str(item.get("kind") or ""), 5)
            == _SEED_KIND_PRIORITY.get(str(top.get("kind") or ""), 5)
        ]
        if top_score >= 85 and len(contenders) == 1:
            node = engine.index.resolve_node(top["stable_id"])
            if node is not None:
                resolved.append(node)
                continue
        ambiguous.append(
            {
                "seed": seed,
                "candidates": [
                    {
                        "stable_id": item.get("stable_id"),
                        "score": item.get("score"),
                        "name": item.get("name"),
                        "kind": item.get("kind"),
                    }
                    for item in ranked[:5]
                ],
                "reason": "ambiguous",
            }
        )
    return resolved, ambiguous


def _best_path(
    engine: GraphQueryEngine,
    seed: GraphNode,
    target: GraphNode,
    *,
    max_depth: int,
) -> dict[str, Any] | None:
    found = engine.paths(seed.stable_id, target.stable_id, max_depth=max_depth, max_paths=3)
    if not found.get("found"):
        return {
            "entity_path": [seed.stable_id, target.stable_id],
            "edge_kinds": ["CLOSURE_MEMBER"],
            "depth": 1,
            "category": _category_for_node(target),
            "cost_tokens": max(8, len(target.stable_id) // 2),
            "noise": _noise_score(target),
            "evidence": 0.4,
        }
    path = found["paths"][0]
    nodes = path.get("nodes") or []
    edges = path.get("edges") or []
    entity_path = [str(node.get("stable_id")) for node in nodes]
    edge_kinds = [str(edge.get("kind")) for edge in edges]
    category = "implementation"
    for kind in edge_kinds:
        if kind in CATEGORY_BY_KIND:
            category = CATEGORY_BY_KIND[kind]
            break
    resolutions = [str(edge.get("resolution") or "exact") for edge in edges]
    evidence = 0.7 if any(item != "exact" for item in resolutions) else 1.0
    cost = max(12, sum(len(str(node.get("stable_id", ""))) for node in nodes) // 2)
    return {
        "entity_path": entity_path,
        "edge_kinds": edge_kinds,
        "depth": max(1, len(edges)),
        "category": category,
        "cost_tokens": cost,
        "noise": max(
            _noise_score(target),
            max((_noise_score_from_id(eid) for eid in entity_path), default=0.0),
        ),
        "evidence": evidence,
    }


def _score_path(
    path_info: dict[str, Any],
    *,
    covered_categories: set[str],
    weights: dict[str, float],
    seed: GraphNode,
) -> float:
    depth = float(path_info["depth"])
    category = str(path_info["category"])
    coverage = 1.0 if category not in covered_categories else 0.15
    relevance = 1.0
    if any(kind in HIGH_PRIORITY_KINDS for kind in path_info.get("edge_kinds", [])):
        relevance += 0.5
    if seed.qualified_name.split(".")[0] in str(path_info["entity_path"][-1]):
        relevance += 0.2
    return (
        weights["relevance"] * relevance
        + weights["coverage"] * coverage
        + weights["evidence"] * float(path_info["evidence"])
        - weights["distance"] * depth
        - weights["noise"] * float(path_info["noise"])
        - weights["cost"] * float(path_info["cost_tokens"])
    )


def _boundaries_from_closure(
    engine: GraphQueryEngine,
    closure: dict[str, Any],
    root_ids: set[int],
    nodes_by_id: dict[int, GraphNode],
) -> list[dict[str, Any]]:
    boundaries: list[dict[str, Any]] = []
    for edge_payload in closure.get("unresolved", [])[:20]:
        source_id = edge_payload.get("source")
        source_node = nodes_by_id.get(source_id) if isinstance(source_id, int) else None
        boundaries.append(
            {
                "source": source_node.stable_id if source_node else source_id,
                "kind": edge_payload.get("kind", "unresolved"),
                "reason": f"resolution={edge_payload.get('resolution', 'unresolved')}",
                "evidence": edge_payload.get("attributes"),
            }
        )
    seed_ids = [nodes_by_id[i].stable_id for i in root_ids if i in nodes_by_id]
    risks = engine.risks(seed_ids or None, limit=15)
    for risk in risks.get("risks", [])[:10]:
        edge = risk.get("edge") if isinstance(risk.get("edge"), dict) else {}
        other = risk.get("other") if isinstance(risk.get("other"), dict) else {}
        source_id = edge.get("source")
        source_node = nodes_by_id.get(source_id) if isinstance(source_id, int) else None
        boundaries.append(
            {
                "source": source_node.stable_id
                if source_node
                else other.get("stable_id") or source_id,
                "kind": edge.get("kind", "dynamic_risk"),
                "reason": "static dynamic-risk cue",
                "evidence": edge.get("attributes") or risk.get("direction"),
            }
        )
    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for item in boundaries:
        key = (item.get("source"), item.get("kind"), item.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:25]


def _category_for_node(node: GraphNode) -> str:
    if node.kind in {"resource"}:
        return "resource"
    if node.kind in {"environment_variable", "config"}:
        return "configuration"
    if node.kind in {"global_state"}:
        return "state"
    if node.kind in {"class", "type"}:
        return "data"
    return "implementation"


def _role_for_category(category: str) -> str:
    return {
        "interface": "api_surface",
        "data": "data_model",
        "configuration": "config_or_env",
        "resource": "resource",
        "dispatch": "registry_or_dispatch",
        "state": "runtime_state",
        "implementation": "supporting_implementation",
    }.get(category, "support")


def _noise_score(node: GraphNode) -> float:
    path = node.span.path if node.span is not None else ""
    blob = f"{node.qualified_name} {path}".casefold()
    return 1.0 if any(marker in blob for marker in NOISE_PATH_MARKERS) else 0.0


def _noise_score_from_id(stable_id: str) -> float:
    blob = stable_id.casefold()
    return 1.0 if any(marker in blob for marker in NOISE_PATH_MARKERS) else 0.0


def _estimate_tokens(payload: dict[str, Any]) -> int:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return max(1, (len(rendered) + 3) // 4)
