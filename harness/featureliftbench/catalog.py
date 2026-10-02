"""Public catalogs for benchmark suites, agents, and methods.

FeatureLiftBench experiments are the product of three first-class registries:

* ``benchmark/suites.toml`` — named task roots and source registries
* ``agent/registry.toml`` — coding runtimes (``--agent``)
* ``method/registry.toml`` — protocols / information arms (``--method`` / ``--arm``)

Adapter and evaluator implementations stay in this package. The catalogs are
the stable ids used by ``scripts/run_experiment.sh`` and
``scripts/run_benchmark.sh``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Iterable
from typing import Mapping

from .agent_adapters import SUPPORTED_AGENTS
from .paths import AGENT_REGISTRY
from .paths import BENCHMARK_SUITES
from .paths import DEFAULT_AGENT_CONFIG_EXAMPLE
from .paths import METHOD_REGISTRY
from .paths import REPO_ROOT

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]


class CatalogError(ValueError):
    """Invalid catalog lookup or registry contents."""


@dataclass(frozen=True)
class AgentSpec:
    id: str
    cli_name: str
    aliases: tuple[str, ...]
    status: str
    paper_table: bool
    adapter: str
    docs: str
    description: str
    pins: str


@dataclass(frozen=True)
class MethodSpec:
    id: str
    aliases: tuple[str, ...]
    status: str
    paper_table: bool
    docs: str
    spec: str
    description: str
    run_agent_flags: tuple[str, ...]
    profiles: Mapping[str, str]


@dataclass(frozen=True)
class SuiteSpec:
    id: str
    aliases: tuple[str, ...]
    tasks_root: str
    source_registry: str
    status: str
    paper_main: bool
    description: str
    task_file: str


@dataclass(frozen=True)
class Catalog:
    agents: Mapping[str, AgentSpec]
    methods: Mapping[str, MethodSpec]
    suites: Mapping[str, SuiteSpec]
    agent_index: Mapping[str, str]
    method_index: Mapping[str, str]
    suite_index: Mapping[str, str]


@dataclass(frozen=True)
class ResolvedRun:
    agent: AgentSpec
    method: MethodSpec
    suite: SuiteSpec | None
    profile: str
    agent_cli: str
    tasks_root: str | None
    source_registry: str | None
    run_agent_flags: tuple[str, ...]


def _require_tomllib() -> Any:
    if tomllib is None:
        raise CatalogError("catalog requires Python 3.11+ (tomllib)")
    return tomllib


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CatalogError(f"catalog file missing: {path}")
    return _require_tomllib().loads(path.read_text(encoding="utf-8"))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    raise CatalogError(f"expected string list, got {type(value).__name__}")


def _mapping_str(value: Any) -> dict[str, str]:
    if not value:
        return {}
    if not isinstance(value, dict):
        raise CatalogError(f"expected table, got {type(value).__name__}")
    return {str(key): str(item) for key, item in value.items()}


def _build_index(items: Mapping[str, Any], *, aliases_of) -> dict[str, str]:
    index: dict[str, str] = {}
    for item_id, spec in items.items():
        keys = {item_id, *aliases_of(spec)}
        for key in keys:
            normalized = str(key).strip()
            if not normalized:
                continue
            previous = index.get(normalized)
            if previous is not None and previous != item_id:
                raise CatalogError(
                    f"duplicate catalog alias {normalized!r} -> {previous} and {item_id}"
                )
            index[normalized] = item_id
            collapsed = normalized.replace("-", "_")
            previous = index.get(collapsed)
            if previous is not None and previous != item_id:
                continue
            index.setdefault(collapsed, item_id)
    return index


def load_catalog(
    *,
    agent_path: Path | None = None,
    method_path: Path | None = None,
    suite_path: Path | None = None,
) -> Catalog:
    agent_data = _load_toml(Path(agent_path) if agent_path else AGENT_REGISTRY)
    method_data = _load_toml(Path(method_path) if method_path else METHOD_REGISTRY)
    suite_data = _load_toml(Path(suite_path) if suite_path else BENCHMARK_SUITES)

    agents: dict[str, AgentSpec] = {}
    for agent_id, raw in (agent_data.get("agents") or {}).items():
        row = raw or {}
        aliases = _string_tuple(row.get("aliases"))
        if agent_id not in aliases:
            aliases = (agent_id, *aliases)
        agents[str(agent_id)] = AgentSpec(
            id=str(agent_id),
            cli_name=str(row.get("cli_name") or agent_id),
            aliases=aliases,
            status=str(row.get("status") or "internal"),
            paper_table=bool(row.get("paper_table")),
            adapter=str(row.get("adapter") or ""),
            docs=str(row.get("docs") or ""),
            description=str(row.get("description") or ""),
            pins=str(row.get("pins") or ""),
        )

    methods: dict[str, MethodSpec] = {}
    for method_id, raw in (method_data.get("methods") or {}).items():
        row = raw or {}
        aliases = _string_tuple(row.get("aliases"))
        if method_id not in aliases:
            aliases = (method_id, *aliases)
        methods[str(method_id)] = MethodSpec(
            id=str(method_id),
            aliases=aliases,
            status=str(row.get("status") or "internal"),
            paper_table=bool(row.get("paper_table")),
            docs=str(row.get("docs") or ""),
            spec=str(row.get("spec") or ""),
            description=str(row.get("description") or ""),
            run_agent_flags=_string_tuple(row.get("run_agent_flags")),
            profiles=_mapping_str(row.get("profiles")),
        )

    suites: dict[str, SuiteSpec] = {}
    for suite_id, raw in (suite_data.get("suites") or {}).items():
        row = raw or {}
        aliases = _string_tuple(row.get("aliases"))
        if suite_id not in aliases:
            aliases = (suite_id, *aliases)
        suites[str(suite_id)] = SuiteSpec(
            id=str(suite_id),
            aliases=aliases,
            tasks_root=str(row.get("tasks_root") or ""),
            source_registry=str(row.get("source_registry") or ""),
            status=str(row.get("status") or "internal"),
            paper_main=bool(row.get("paper_main")),
            description=str(row.get("description") or ""),
            task_file=str(row.get("task_file") or ""),
        )

    return Catalog(
        agents=agents,
        methods=methods,
        suites=suites,
        agent_index=_build_index(agents, aliases_of=lambda spec: spec.aliases),
        method_index=_build_index(methods, aliases_of=lambda spec: spec.aliases),
        suite_index=_build_index(suites, aliases_of=lambda spec: spec.aliases),
    )


def _lookup(index: Mapping[str, str], name: str, *, kind: str) -> str:
    raw = (name or "").strip()
    if not raw:
        raise CatalogError(f"{kind} id is required")
    item_id = index.get(raw) or index.get(raw.replace("-", "_"))
    if item_id is None:
        known = ", ".join(sorted(set(index.values())))
        raise CatalogError(f"unknown {kind} {name!r}; known: {known}")
    return item_id


def get_agent(catalog: Catalog, name: str) -> AgentSpec:
    return catalog.agents[_lookup(catalog.agent_index, name, kind="agent")]


def get_method(catalog: Catalog, name: str) -> MethodSpec:
    return catalog.methods[_lookup(catalog.method_index, name, kind="method")]


def get_suite(catalog: Catalog, name: str) -> SuiteSpec:
    return catalog.suites[_lookup(catalog.suite_index, name, kind="benchmark")]


def profile_for(method: MethodSpec, agent: AgentSpec) -> str:
    profile = method.profiles.get(agent.id)
    if not profile:
        available = ", ".join(sorted(method.profiles)) or "(none)"
        raise CatalogError(
            f"method {method.id!r} has no profile for agent {agent.id!r}; "
            f"configured agents: {available}"
        )
    return profile


def resolve_run(
    *,
    agent: str,
    method: str,
    benchmark: str | None = None,
    catalog: Catalog | None = None,
) -> ResolvedRun:
    loaded = catalog or load_catalog()
    agent_spec = get_agent(loaded, agent)
    method_spec = get_method(loaded, method)
    suite_spec = get_suite(loaded, benchmark) if benchmark else None
    return ResolvedRun(
        agent=agent_spec,
        method=method_spec,
        suite=suite_spec,
        profile=profile_for(method_spec, agent_spec),
        agent_cli=agent_spec.cli_name,
        tasks_root=suite_spec.tasks_root if suite_spec else None,
        source_registry=suite_spec.source_registry if suite_spec else None,
        run_agent_flags=method_spec.run_agent_flags,
    )


def resolved_payload(resolved: ResolvedRun) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "agent_id": resolved.agent.id,
        "agent_cli": resolved.agent_cli,
        "agent_status": resolved.agent.status,
        "agent_paper_table": resolved.agent.paper_table,
        "method_id": resolved.method.id,
        "method_status": resolved.method.status,
        "method_paper_table": resolved.method.paper_table,
        "profile": resolved.profile,
        "run_agent_flags": list(resolved.run_agent_flags),
        "paper_table": bool(
            resolved.agent.paper_table and resolved.method.paper_table
        ),
    }
    if resolved.suite is not None:
        payload.update(
            {
                "benchmark_id": resolved.suite.id,
                "benchmark_status": resolved.suite.status,
                "benchmark_paper_main": resolved.suite.paper_main,
                "tasks_root": resolved.tasks_root,
                "source_registry": resolved.source_registry,
                "task_file": resolved.suite.task_file or "",
            }
        )
    return payload


def emit_bash(payload: Mapping[str, Any]) -> str:
    lines = [
        f"CATALOG_AGENT_ID={shlex.quote(str(payload.get('agent_id', '')))}",
        f"CATALOG_AGENT_CLI={shlex.quote(str(payload.get('agent_cli', '')))}",
        f"CATALOG_METHOD_ID={shlex.quote(str(payload.get('method_id', '')))}",
        f"CATALOG_PROFILE={shlex.quote(str(payload.get('profile', '')))}",
        f"CATALOG_TASKS_ROOT={shlex.quote(str(payload.get('tasks_root', '') or ''))}",
        f"CATALOG_SOURCE_REGISTRY={shlex.quote(str(payload.get('source_registry', '') or ''))}",
        f"CATALOG_TASK_FILE={shlex.quote(str(payload.get('task_file', '') or ''))}",
        f"CATALOG_BENCHMARK_ID={shlex.quote(str(payload.get('benchmark_id', '') or ''))}",
        f"CATALOG_PAPER_TABLE={shlex.quote('1' if payload.get('paper_table') else '0')}",
    ]
    return "\n".join(lines) + "\n"


def check_catalog(catalog: Catalog | None = None) -> list[str]:
    loaded = catalog or load_catalog()
    errors: list[str] = []
    supported = set(SUPPORTED_AGENTS)
    example = DEFAULT_AGENT_CONFIG_EXAMPLE
    profiles: set[str] = set()
    if example.is_file() and tomllib is not None:
        data = tomllib.loads(example.read_text(encoding="utf-8"))
        profiles = set((data.get("profiles") or {}).keys())

    for agent in loaded.agents.values():
        if agent.cli_name not in supported:
            errors.append(
                f"agent {agent.id}: cli_name {agent.cli_name!r} is not in SUPPORTED_AGENTS"
            )
        if agent.pins:
            pin_path = REPO_ROOT / agent.pins
            if not pin_path.is_file():
                errors.append(f"agent {agent.id}: pins missing {agent.pins}")

    for method in loaded.methods.values():
        if not method.run_agent_flags:
            errors.append(f"method {method.id}: run_agent_flags is empty")
        if method.spec:
            spec_path = REPO_ROOT / method.spec
            if not spec_path.is_file():
                errors.append(f"method {method.id}: spec missing {method.spec}")
        for agent_id, profile in method.profiles.items():
            if agent_id not in loaded.agents:
                errors.append(
                    f"method {method.id}: profile agent {agent_id!r} is not in agent/registry.toml"
                )
            if profiles and profile not in profiles:
                errors.append(
                    f"method {method.id}: profile {profile!r} is not in agents.example.toml"
                )

    for suite in loaded.suites.values():
        if not suite.tasks_root:
            errors.append(f"suite {suite.id}: tasks_root is empty")
            continue
        tasks_root = REPO_ROOT / suite.tasks_root
        if not tasks_root.is_dir():
            errors.append(f"suite {suite.id}: tasks_root missing {suite.tasks_root}")
        if suite.source_registry:
            registry = REPO_ROOT / suite.source_registry
            if not registry.is_file():
                errors.append(
                    f"suite {suite.id}: source_registry missing {suite.source_registry}"
                )
        if suite.task_file:
            task_file = REPO_ROOT / suite.task_file
            if not task_file.is_file():
                errors.append(f"suite {suite.id}: task_file missing {suite.task_file}")
            else:
                ids = [
                    line.strip()
                    for line in task_file.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                if not ids:
                    errors.append(f"suite {suite.id}: task_file is empty")
                seen: set[str] = set()
                for task_id in ids:
                    if task_id in seen:
                        errors.append(f"suite {suite.id}: duplicate task_id {task_id}")
                    seen.add(task_id)
                    if not (tasks_root / task_id / "metadata.json").is_file():
                        errors.append(
                            f"suite {suite.id}: task_file id missing {task_id}"
                        )

    paper_agents = sorted(
        agent.id for agent in loaded.agents.values() if agent.paper_table
    )
    paper_methods = sorted(
        method.id for method in loaded.methods.values() if method.paper_table
    )
    if paper_agents != ["openhands"]:
        errors.append(
            f"paper_table agents must be exactly ['openhands'], got {paper_agents}"
        )
    if paper_methods != ["main"]:
        errors.append(
            f"paper_table methods must be exactly ['main'], got {paper_methods}"
        )
    return errors


def _print_table(title: str, rows: Iterable[tuple[str, ...]]) -> None:
    print(title)
    for row in rows:
        print("  " + "  ".join(row))


def cmd_list(kind: str = "all") -> int:
    catalog = load_catalog()
    if kind in {"all", "benchmarks"}:
        _print_table(
            "benchmarks",
            (
                (
                    suite.id,
                    suite.status,
                    "paper-main" if suite.paper_main else "-",
                    suite.tasks_root,
                )
                for suite in catalog.suites.values()
            ),
        )
    if kind in {"all", "agents"}:
        _print_table(
            "agents",
            (
                (
                    agent.id,
                    agent.cli_name,
                    agent.status,
                    "paper-table" if agent.paper_table else "-",
                )
                for agent in catalog.agents.values()
            ),
        )
    if kind in {"all", "methods"}:
        _print_table(
            "methods",
            (
                (
                    method.id,
                    method.status,
                    "paper-table" if method.paper_table else "-",
                    ",".join(sorted(method.profiles)),
                )
                for method in catalog.methods.values()
            ),
        )
    return 0


def cmd_resolve(
    *,
    agent: str,
    method: str,
    benchmark: str | None,
    fmt: str,
) -> int:
    try:
        resolved = resolve_run(agent=agent, method=method, benchmark=benchmark)
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload = resolved_payload(resolved)
    if fmt == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif fmt == "bash":
        sys.stdout.write(emit_bash(payload))
    else:
        print(
            f"{payload['agent_cli']} × {payload['method_id']}"
            + (f" × {payload.get('benchmark_id')}" if payload.get("benchmark_id") else "")
        )
        print(f"profile: {payload['profile']}")
        if payload.get("tasks_root"):
            print(f"tasks:   {payload['tasks_root']}")
            print(f"sources: {payload['source_registry']}")
        print("flags:   " + " ".join(payload["run_agent_flags"]))
    return 0


def cmd_flags(*, method: str) -> int:
    try:
        spec = get_method(load_catalog(), method)
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for flag in spec.run_agent_flags:
        print(flag)
    return 0


def cmd_profile(*, agent: str, method: str) -> int:
    try:
        resolved = resolve_run(agent=agent, method=method)
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(resolved.profile)
    return 0


def cmd_check() -> int:
    errors = check_catalog()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    print("catalog ok")
    return 0


def cmd_suite(*, benchmark: str, fmt: str) -> int:
    try:
        suite = get_suite(load_catalog(), benchmark)
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload = {
        "benchmark_id": suite.id,
        "tasks_root": suite.tasks_root,
        "source_registry": suite.source_registry,
        "status": suite.status,
        "paper_main": suite.paper_main,
        "task_file": suite.task_file,
    }
    if fmt == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif fmt == "bash":
        sys.stdout.write(
            "".join(
                [
                    f"CATALOG_BENCHMARK_ID={shlex.quote(suite.id)}\n",
                    f"CATALOG_TASKS_ROOT={shlex.quote(suite.tasks_root)}\n",
                    f"CATALOG_SOURCE_REGISTRY={shlex.quote(suite.source_registry)}\n",
                    f"CATALOG_TASK_FILE={shlex.quote(suite.task_file)}\n",
                ]
            )
        )
    else:
        print(f"{suite.id}: {suite.tasks_root} ({suite.source_registry})")
    return 0


def cmd_agent(*, agent: str, fmt: str) -> int:
    try:
        spec = get_agent(load_catalog(), agent)
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload = {
        "agent_id": spec.id,
        "agent_cli": spec.cli_name,
        "status": spec.status,
        "paper_table": spec.paper_table,
    }
    if fmt == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif fmt == "bash":
        sys.stdout.write(
            "".join(
                [
                    f"CATALOG_AGENT_ID={shlex.quote(spec.id)}\n",
                    f"CATALOG_AGENT_CLI={shlex.quote(spec.cli_name)}\n",
                ]
            )
        )
    else:
        print(f"{spec.id} -> --agent {spec.cli_name}")
    return 0


def add_catalog_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    parser = subparsers.add_parser(
        "catalog",
        help="list or resolve benchmark × agent × method",
    )
    catalog_sub = parser.add_subparsers(dest="catalog_command", required=True)

    list_parser = catalog_sub.add_parser("list", help="print registered ids")
    list_parser.add_argument(
        "--kind",
        choices=("all", "agents", "methods", "benchmarks"),
        default="all",
    )

    resolve_parser = catalog_sub.add_parser(
        "resolve",
        help="resolve --agent and --method (optional --benchmark)",
    )
    resolve_parser.add_argument("--agent", required=True)
    resolve_parser.add_argument("--method", required=True)
    resolve_parser.add_argument("--benchmark")
    resolve_parser.add_argument(
        "--format",
        dest="fmt",
        choices=("text", "json", "bash"),
        default="text",
    )

    flags_parser = catalog_sub.add_parser(
        "flags",
        help="print run-agent flags for a method, one per line",
    )
    flags_parser.add_argument("--method", required=True)

    profile_parser = catalog_sub.add_parser(
        "profile",
        help="print the agent profile for a method",
    )
    profile_parser.add_argument("--agent", required=True)
    profile_parser.add_argument("--method", required=True)

    catalog_sub.add_parser("check", help="validate catalogs against adapters and profiles")

    suite_parser = catalog_sub.add_parser(
        "suite",
        help="resolve a named --benchmark / --suite root",
    )
    suite_parser.add_argument("--benchmark", required=True)
    suite_parser.add_argument(
        "--format",
        dest="fmt",
        choices=("text", "json", "bash"),
        default="text",
    )

    agent_parser = catalog_sub.add_parser(
        "agent",
        help="normalize an --agent alias to the CLI adapter name",
    )
    agent_parser.add_argument("--agent", required=True)
    agent_parser.add_argument(
        "--format",
        dest="fmt",
        choices=("text", "json", "bash"),
        default="text",
    )


def dispatch_catalog(args: argparse.Namespace) -> int:
    command = args.catalog_command
    if command == "list":
        return cmd_list(args.kind)
    if command == "resolve":
        return cmd_resolve(
            agent=args.agent,
            method=args.method,
            benchmark=args.benchmark,
            fmt=args.fmt,
        )
    if command == "flags":
        return cmd_flags(method=args.method)
    if command == "profile":
        return cmd_profile(agent=args.agent, method=args.method)
    if command == "check":
        return cmd_check()
    if command == "suite":
        return cmd_suite(benchmark=args.benchmark, fmt=args.fmt)
    if command == "agent":
        return cmd_agent(agent=args.agent, fmt=args.fmt)
    raise CatalogError(f"unknown catalog command: {command}")
