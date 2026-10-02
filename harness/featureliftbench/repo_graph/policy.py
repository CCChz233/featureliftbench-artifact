"""Opt-in Repository Semantic Graph policy shared by config and runners."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


MODE_ENV = "FEATURELIFTBENCH_REPO_GRAPH_MODE"
TRANSPORT_ENV = "FEATURELIFTBENCH_REPO_GRAPH_TRANSPORT"
FAIL_FAST_ENV = "FEATURELIFTBENCH_REPO_GRAPH_FAIL_FAST"
BOOTSTRAP_MAX_NODES_ENV = "FEATURELIFTBENCH_REPO_GRAPH_BOOTSTRAP_MAX_NODES"
BOOTSTRAP_MAX_CHARS_ENV = "FEATURELIFTBENCH_REPO_GRAPH_BOOTSTRAP_MAX_CHARS"
QUERY_MAX_CHARS_ENV = "FEATURELIFTBENCH_REPO_GRAPH_QUERY_MAX_CHARS"
ROOT_ENV = "FEATURELIFTBENCH_REPO_GRAPH_ROOT"
CACHE_DIR_ENV = "FEATURELIFTBENCH_REPO_GRAPH_CACHE_DIR"
BOOTSTRAP_STYLE_ENV = "FEATURELIFTBENCH_RSG_BOOTSTRAP"
BUDGET_TOKENS_ENV = "FEATURELIFTBENCH_RSG_BUDGET_TOKENS"
INSPECT_MAX_CHARS_ENV = "FEATURELIFTBENCH_RSG_INSPECT_MAX_CHARS"
VIEW_ENV = "FEATURELIFTBENCH_RSG_VIEW"

VALID_MODES = frozenset({"disabled", "static", "closure", "evidence"})
VALID_TRANSPORTS = frozenset({"cli", "inprocess"})
VALID_BOOTSTRAPS = frozenset({"tool_only", "auto_support"})
VALID_VIEWS = frozenset({"operational_support", "none"})


@dataclass(frozen=True)
class RepoGraphPolicy:
    mode: str = "disabled"
    transport: str = "cli"
    fail_fast: bool = True
    bootstrap_max_nodes: int = 30
    bootstrap_max_chars: int = 4_096
    query_max_chars: int = 12_000
    # Design v2 orthogonal fields (OpenHands formal default: tool_only).
    bootstrap: str = "tool_only"
    view: str = "operational_support"
    budget_tokens: int = 8_000
    inspect_max_chars: int = 4_000

    @property
    def enabled(self) -> bool:
        return self.mode != "disabled"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "featureliftbench.repo_graph.policy.v2",
            **asdict(self),
            "enabled": self.enabled,
        }

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None) -> RepoGraphPolicy:
        values = env or {}
        mode = values.get(MODE_ENV, "disabled").strip().lower() or "disabled"
        transport = values.get(TRANSPORT_ENV, "cli").strip().lower() or "cli"
        if mode not in VALID_MODES:
            raise ValueError(f"unknown repository graph mode: {mode}")
        if transport not in VALID_TRANSPORTS:
            raise ValueError(f"unknown repository graph transport: {transport}")
        fail_fast = _parse_bool(values.get(FAIL_FAST_ENV), default=True, name="repo_graph_fail_fast")
        bootstrap_max_nodes = _parse_positive_int(
            values.get(BOOTSTRAP_MAX_NODES_ENV),
            default=30,
            name="repo_graph_bootstrap_max_nodes",
        )
        bootstrap_max_chars = _parse_positive_int(
            values.get(BOOTSTRAP_MAX_CHARS_ENV),
            default=4_096,
            name="repo_graph_bootstrap_max_chars",
        )
        query_max_chars = _parse_positive_int(
            values.get(QUERY_MAX_CHARS_ENV),
            default=12_000,
            name="repo_graph_query_max_chars",
        )
        bootstrap = (
            values.get(BOOTSTRAP_STYLE_ENV, "tool_only").strip().lower() or "tool_only"
        )
        view = (
            values.get(VIEW_ENV, "operational_support").strip().lower()
            or "operational_support"
        )
        if bootstrap not in VALID_BOOTSTRAPS:
            raise ValueError(f"unknown rsg bootstrap style: {bootstrap}")
        if view not in VALID_VIEWS:
            raise ValueError(f"unknown rsg view: {view}")
        budget_tokens = _parse_positive_int(
            values.get(BUDGET_TOKENS_ENV),
            default=8_000,
            name="rsg_budget_tokens",
        )
        inspect_max_chars = _parse_positive_int(
            values.get(INSPECT_MAX_CHARS_ENV),
            default=4_000,
            name="rsg_inspect_max_chars",
        )
        if query_max_chars < 512:
            raise ValueError("repo_graph_query_max_chars must be at least 512")
        if bootstrap_max_chars < 1_024:
            raise ValueError("repo_graph_bootstrap_max_chars must be at least 1024")
        if budget_tokens < 256:
            raise ValueError("rsg_budget_tokens must be at least 256")
        if inspect_max_chars < 256:
            raise ValueError("rsg_inspect_max_chars must be at least 256")
        return cls(
            mode=mode,
            transport=transport,
            fail_fast=fail_fast,
            bootstrap_max_nodes=bootstrap_max_nodes,
            bootstrap_max_chars=bootstrap_max_chars,
            query_max_chars=query_max_chars,
            bootstrap=bootstrap,
            view=view,
            budget_tokens=budget_tokens,
            inspect_max_chars=inspect_max_chars,
        )


def _parse_bool(value: str | None, *, default: bool, name: str) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _parse_positive_int(value: str | None, *, default: int, name: str) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed
