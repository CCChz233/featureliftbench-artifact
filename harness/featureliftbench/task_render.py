"""Render Agent-visible TASK.md from metadata.public_spec."""

from __future__ import annotations

from typing import Any

BEHAVIOR_MARKER_START = "<!-- featureliftbench:behavior-clauses:start -->"
BEHAVIOR_MARKER_END = "<!-- featureliftbench:behavior-clauses:end -->"

COMPLETE_FEATURE_RESPONSIBILITY_VERSION = "featureliftbench.complete_feature_responsibility.v1"
COMPLETE_FEATURE_RESPONSIBILITY_MARKER = (
    f"<!-- {COMPLETE_FEATURE_RESPONSIBILITY_VERSION} -->"
)
COMPLETE_FEATURE_RESPONSIBILITY_HEADING = "## Complete Feature Responsibility"
COMPLETE_FEATURE_RESPONSIBILITY_TEXT = """Treat the requested feature as a complete task-scoped module, not as a list of isolated examples. You are responsible for inspecting the full upstream repository—including its source, tests, documentation, examples, configuration, and resources—to discover the implementation locations, observable contract, edge and error semantics, state behavior, and transitive code and data closure needed to preserve the feature.

The Target API, Required Behavior, Constraints, and Exclusions below define the exhaustive scope boundary. Every obligation inside that boundary is mandatory, while unrelated upstream functionality is out of scope. Examples illustrate required semantics; they are not a small case list to fit. A submission is incomplete if it implements only the main path or passes self-written smoke tests while omitting any in-scope behavior, boundary condition, exception distinction, state transition, required member or resource, dependency, or isolation obligation."""


def _complete_feature_responsibility_section() -> str:
    return (
        f"{COMPLETE_FEATURE_RESPONSIBILITY_MARKER}\n"
        f"{COMPLETE_FEATURE_RESPONSIBILITY_HEADING}\n\n"
        f"{COMPLETE_FEATURE_RESPONSIBILITY_TEXT}\n\n"
    )


def _format_api_import_block(required_api: list[dict[str, Any]]) -> str:
    symbols: list[str] = []
    for entry in required_api:
        path = str(entry.get("path", ""))
        if not path.startswith("featurelifted."):
            continue
        suffix = path.removeprefix("featurelifted.")
        if suffix.startswith("__") and suffix.endswith("__"):
            symbols.append(suffix)
        else:
            symbols.append(suffix.split(".")[0])
    unique = sorted(set(symbols), key=lambda item: (item.startswith("__"), item.lower(), item))
    lines = ",\n    ".join(unique)
    return f"from featurelifted import (\n    {lines},\n)"


def _format_required_api_details(required_api: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []

    def append_entry(
        entry: dict[str, Any],
        *,
        depth: int = 0,
        parent_kind: str | None = None,
    ) -> None:
        path = str(entry.get("path", ""))
        kind = str(entry.get("kind", ""))
        signature = entry.get("signature")
        name = path.removeprefix("featurelifted.")
        prefix = ("  " * depth) + "-"
        if kind in {"function", "method", "callable"}:
            if isinstance(signature, str):
                lines.append(f"{prefix} `{name}{signature}`")
            else:
                lines.append(f"{prefix} `{name}` callable must exist")
        elif kind == "exception":
            lines.append(f"{prefix} `{name}` must be importable and raisable")
        elif kind == "class":
            if isinstance(signature, str):
                lines.append(f"{prefix} `{name}{signature}` class constructor")
            else:
                lines.append(f"{prefix} `{name}` class must be importable")
        elif kind == "module":
            lines.append(f"{prefix} `{name}` module must be importable")
        elif kind == "attribute":
            scope = " on instances" if parent_kind == "class" else ""
            lines.append(f"{prefix} `{name}` attribute must exist{scope}")
        elif kind == "constant":
            lines.append(f"{prefix} `{name}` constant must exist")
        else:
            lines.append(f"{prefix} `{name}` {kind or 'API object'} must exist")

        members = entry.get("members")
        if isinstance(members, list):
            for member in members:
                if isinstance(member, dict):
                    append_entry(member, depth=depth + 1, parent_kind=kind)

    for entry in required_api:
        if isinstance(entry, dict):
            append_entry(entry)
    return lines


def render_public_task(
    metadata: dict[str, Any],
    *,
    include_behavior_clauses: bool = True,
    include_public_hidden_note: bool = True,
    include_complete_feature_responsibility: bool = False,
) -> str:
    public_spec = metadata.get("public_spec")
    if not isinstance(public_spec, dict):
        raise ValueError("metadata.public_spec is required to render TASK.md")

    source = metadata.get("source") if isinstance(metadata.get("source"), dict) else {}
    source_name = str(source.get("name", "upstream"))
    title = str(public_spec.get("title", metadata.get("task_id", "FeatureLift Task")))
    summary = str(public_spec.get("summary", "")).strip()
    required_api = public_spec.get("required_api")
    if not isinstance(required_api, list):
        required_api = []
    behaviors = public_spec.get("behaviors")
    if not isinstance(behaviors, list):
        behaviors = []
    exclusions = public_spec.get("exclusions")
    if not isinstance(exclusions, list):
        exclusions = []
    forbidden = public_spec.get("forbidden")
    if not isinstance(forbidden, dict):
        forbidden = {}
    forbidden_imports = [
        str(item) for item in (forbidden.get("imports") or []) if isinstance(item, str)
    ]
    forbidden_paths = [
        str(item) for item in (forbidden.get("paths") or []) if isinstance(item, str)
    ]

    parts = [
        f"# FeatureLift Task: {title}\n\n",
        summary,
        "\n\n",
    ]
    if include_complete_feature_responsibility:
        parts.append(_complete_feature_responsibility_section())
    parts.extend(
        [
            "The submitted implementation must not import the upstream package or read from "
            "`repo/` at runtime, must not use the network, and must not depend on external services. "
            "Use only the standard library unless the task lockfile allows otherwise.\n\n",
            "## Target API\n\n",
            "```python\n",
            _format_api_import_block(required_api),
            "\n```\n\n",
        ]
    )

    api_details = _format_required_api_details(required_api)
    if api_details:
        parts.extend(["## Required API Details\n\n", "\n".join(api_details), "\n\n"])

    behavior_lines = [
        f"- {entry.get('text')}"
        for entry in behaviors
        if isinstance(entry, dict) and isinstance(entry.get("text"), str)
    ]
    if behavior_lines:
        parts.extend(["## Required Behavior\n\n", "\n".join(behavior_lines), "\n\n"])

    constraint_lines = []
    if forbidden_imports:
        constraint_lines.append(f"- Forbidden imports: `{', '.join(forbidden_imports)}`.")
    if forbidden_paths:
        constraint_lines.append(f"- Forbidden path access: `{', '.join(forbidden_paths)}`.")
    for item in exclusions:
        constraint_lines.append(f"- Do not implement {item}.")
    if constraint_lines:
        parts.extend(["## Constraints\n\n", "\n".join(constraint_lines), "\n\n"])

    note = public_spec.get("public_vs_hidden_note")
    if include_public_hidden_note and isinstance(note, str) and note.strip():
        parts.extend(["## Public vs Hidden Tests\n\n", note.strip(), "\n\n"])

    if include_behavior_clauses and behaviors:
        parts.extend(
            [
                BEHAVIOR_MARKER_START,
                "\n## Public Behavior Contract\n\n",
                "The stable clause IDs below define the public behavior contract. "
                "Hidden tests may exercise these clauses but do not introduce additional requirements.\n\n",
            ]
        )
        for entry in behaviors:
            if not isinstance(entry, dict):
                continue
            behavior_id = entry.get("id")
            text = entry.get("text")
            if isinstance(behavior_id, str) and isinstance(text, str):
                parts.append(f"- **{behavior_id}** — {text}\n")
        isolation = public_spec.get("isolation_behavior")
        if isinstance(isolation, dict):
            behavior_id = isolation.get("id")
            text = isolation.get("text")
            if isinstance(behavior_id, str) and isinstance(text, str):
                parts.append(f"- **{behavior_id}** — {text}\n")
        parts.extend([BEHAVIOR_MARKER_END, "\n"])

    if source_name and source_name not in summary:
        _ = source_name  # reserved for future source-specific footer
    return "".join(parts)


def render_agent_workspace_task(
    metadata: dict[str, Any],
    *,
    mount_public_tests: bool = False,
    source_entrypoints: list[str] | None = None,
) -> str:
    """Render the TASK.md content placed in an agent workspace for compliant tasks."""

    text = render_public_task(
        metadata,
        include_complete_feature_responsibility=True,
    )
    if source_entrypoints:
        text += (
            "\n## Source Entrypoints — Entrypoint-Hint Ablation\n\n"
            "This diagnostic arm provides frozen upstream implementation anchors:\n\n"
            + "".join(f"- `{item}`\n" for item in source_entrypoints)
        )
    if not mount_public_tests:
        text += (
            "\n## Agent Workspace Note\n\n"
            "Benchmark-authored evaluator tests are not included in this workspace. You may "
            "inspect upstream tests, documentation, and examples that exist under `repo/`, "
            "and you may write and run your own tests. Do not attempt to locate evaluator tests.\n"
        )
    return text
