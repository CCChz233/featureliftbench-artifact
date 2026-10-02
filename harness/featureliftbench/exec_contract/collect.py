"""Orchestrate upstream test selection + Docker instrumentation."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from ..agent_docker import (
    CONTAINER_HARNESS,
    CONTAINER_WORKSPACE,
    DEFAULT_AGENT_DOCKER_CPUS,
    DEFAULT_AGENT_DOCKER_MEMORY,
    DEFAULT_AGENT_DOCKER_NETWORK,
    DEFAULT_AGENT_DOCKER_PIDS,
    DEFAULT_AGENT_DOCKER_TMPFS,
    DEFAULT_AGENT_IMAGE,
    HARNESS_ROOT,
    _env_default,
    _uid_gid,
)
from .common import COLLECT_META
from .common import DEFAULT_MAX_TEST_FILES
from .common import FACTS_FILE
from .common import PYTEST_REPORT
from .common import RUNTIME_DIR
from .common import TRACE_JSONL
from .common import dumps_pretty
from .common import ensure_dir
from .common import flatten_required_api
from .common import is_noise_event
from .common import keywords_from_public_spec
from .common import scaled_collect_timeout
from .common import source_entrypoint_names
from .runtime_doctor import build_runtime_plan
from .select_tests import select_upstream_tests


def _guess_watch_prefixes(repo: Path, public_spec: dict[str, Any] | None) -> list[str]:
    """Path-like watch prefixes only (never free-text keywords)."""

    prefixes: list[str] = []
    entrypoint_prefixes: list[str] = []
    for ep in source_entrypoint_names(public_spec):
        parts = [part for part in ep.split(".") if part]
        if len(parts) >= 2:
            module_parts = parts[:-1]
            entrypoint_prefixes.append(
                "/" + "/".join(module_parts) + ".py"
            )
            entrypoint_prefixes.append(
                "/src/" + "/".join(module_parts) + ".py"
            )
    if entrypoint_prefixes:
        prefixes.extend(entrypoint_prefixes)

    skip = {"tests", "test", "docs", "examples", "scripts", "benchmarks", "ci"}
    if repo.is_dir() and not entrypoint_prefixes:
        for child in sorted(repo.iterdir()):
            if child.is_dir() and (child / "__init__.py").exists():
                if child.name not in skip:
                    prefixes.append(f"/{child.name}/")
        src = repo / "src"
        if src.is_dir():
            for child in sorted(src.iterdir()):
                if child.is_dir() and (
                    (child / "__init__.py").exists() or any(child.glob("*.py"))
                ):
                    prefixes.append(f"/src/{child.name}/")
                    prefixes.append(f"/{child.name}/")
    # de-dupe preserve order
    out: list[str] = []
    seen: set[str] = set()
    for p in prefixes:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out[:20]


def collect_upstream_runtime(
    workspace_dir: str | Path,
    public_spec: dict[str, Any] | None,
    *,
    docker_image: str | None = None,
    max_test_files: int = DEFAULT_MAX_TEST_FILES,
    timeout_seconds: int | None = None,
    use_docker: bool = True,
) -> dict[str, Any]:
    """Select and run upstream tests; write runtime_traces/ + RUNTIME_FACTS.md."""

    workspace = Path(workspace_dir).resolve()
    repo = workspace / "repo"
    runtime = ensure_dir(workspace / RUNTIME_DIR)
    selected = select_upstream_tests(repo, public_spec, max_files=max_test_files)
    watch = _guess_watch_prefixes(repo, public_spec)
    runtime_plan = build_runtime_plan(repo, selected)
    effective_timeout = (
        int(timeout_seconds)
        if timeout_seconds is not None
        else scaled_collect_timeout(len(selected))
    )

    meta: dict[str, Any] = {
        "selected_tests": selected,
        "watch_prefixes": watch,
        "keywords": keywords_from_public_spec(public_spec),
        "required_api": flatten_required_api(public_spec),
        "use_docker": use_docker,
        "docker_image": docker_image or DEFAULT_AGENT_IMAGE,
        "timeout_seconds": effective_timeout,
        "trace_quality": "low",
        "runtime_doctor": runtime_plan,
    }

    if not selected:
        meta["error"] = "no upstream tests selected"
        meta["note"] = (
            "Benchmark repo snapshots often omit tests; contracts rely on "
            "public_spec + upstream AST inference."
        )
        (runtime / COLLECT_META).write_text(dumps_pretty(meta), encoding="utf-8")
        _write_facts(workspace, meta, report=None, events=[])
        return meta

    for name in (TRACE_JSONL, PYTEST_REPORT):
        path = runtime / name
        if path.exists():
            path.unlink()

    if use_docker:
        image = (docker_image or "").strip() or DEFAULT_AGENT_IMAGE
        container = f"flb-exec-{uuid.uuid4().hex[:12]}"
        import shlex

        # Keep the dependency environment ephemeral; only compact trace/audit
        # artifacts persist in the benchmark workspace.
        env_python = "/tmp/flb-upstream-env/bin/python"
        project_rel = str(runtime_plan.get("project_root") or ".")
        project_path = (
            "/flb/workspace/repo"
            if project_rel == "."
            else f"/flb/workspace/repo/{project_rel}"
        )
        extras = [
            str(item)
            for item in runtime_plan.get("project_extras") or []
            if str(item).strip()
        ]
        project_requirement = project_path
        if extras:
            project_requirement += f"[{','.join(extras)}]"

        # Build an isolated upstream runtime from the repository's own
        # pyproject metadata. Installation failures are fatal and visible.
        parts = [
            "set -e",
            "export PIP_DISABLE_PIP_VERSION_CHECK=1",
            "export SETUPTOOLS_SCM_PRETEND_VERSION=99.0",
            "python -m venv /tmp/flb-upstream-env",
            f"{env_python} -m pip install -q setuptools wheel packaging",
        ]
        build_requirements = [
            str(item)
            for item in runtime_plan.get("build_requirements") or []
            if str(item).strip()
        ]
        if build_requirements:
            build_args = " ".join(
                shlex.quote(item) for item in build_requirements
            )
            parts.append(f"{env_python} -m pip install -q {build_args}")
        for sibling in runtime_plan.get("sibling_projects") or []:
            sibling_path = f"/flb/workspace/repo/{str(sibling).strip('/')}"
            parts.append(
                f"{env_python} -m pip install -q --no-build-isolation "
                f"{shlex.quote(sibling_path)}"
            )
        parts.append(
            f"{env_python} -m pip install -q {shlex.quote(project_requirement)} "
            f"|| {env_python} -m pip install -q --no-build-isolation "
            f"{shlex.quote(project_requirement)}"
        )
        requirements = [
            str(item)
            for item in runtime_plan.get("test_requirements") or []
            if str(item).strip()
        ]
        if requirements:
            req_args = " ".join(shlex.quote(item) for item in requirements)
            parts.append(f"{env_python} -m pip install -q {req_args}")
        parts.extend(
            [
            "export PYTHONPATH=/flb/harness",
            f"{env_python} -m featureliftbench.exec_contract.instrument "
            "--trace "
            "--repo /flb/workspace/repo "
            f"--out /flb/workspace/{RUNTIME_DIR}",
            ]
        )
        cmd = parts[-1]
        for prefix in watch:
            cmd += f" --watch {shlex.quote(prefix)}"
        for plugin in runtime_plan.get("required_pytest_plugins") or []:
            cmd += f" --plugin {shlex.quote(str(plugin))}"
        cmd += " --"
        for rel in selected:
            cmd += f" {shlex.quote(rel)}"
        parts[-1] = cmd
        inner = "; ".join(parts)
        tmpfs_parts = [
            part
            for part in _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_TMPFS",
                DEFAULT_AGENT_DOCKER_TMPFS,
            ).split(",")
            if part != "noexec"
        ]
        if "exec" not in tmpfs_parts:
            tmpfs_parts.append("exec")
        collector_tmpfs = ",".join(tmpfs_parts)
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container,
            "--network",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_NETWORK",
                DEFAULT_AGENT_DOCKER_NETWORK,
            ),
            "--memory",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_MEMORY",
                DEFAULT_AGENT_DOCKER_MEMORY,
            ),
            "--cpus",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_CPUS", DEFAULT_AGENT_DOCKER_CPUS
            ),
            "--pids-limit",
            _env_default(
                "FEATURELIFTBENCH_AGENT_DOCKER_PIDS", DEFAULT_AGENT_DOCKER_PIDS
            ),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--tmpfs",
            collector_tmpfs,
            "--user",
            _uid_gid(),
            "-w",
            str(CONTAINER_WORKSPACE),
            "-v",
            f"{workspace}:{CONTAINER_WORKSPACE}:rw",
            "-v",
            f"{HARNESS_ROOT.resolve()}:{CONTAINER_HARNESS}:ro",
            "-e",
            "PYTHONPATH=/flb/harness:/flb/workspace/repo/src:/flb/workspace/repo",
            image,
            "bash",
            "-lc",
            inner,
        ]
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=max(1, int(effective_timeout)),
            )
            meta["collector_returncode"] = proc.returncode
            meta["collector_stdout_tail"] = (proc.stdout or "")[-8000:]
            meta["collector_stderr_tail"] = (proc.stderr or "")[-8000:]
        except subprocess.TimeoutExpired as exc:
            meta["collector_returncode"] = 124
            meta["collector_timed_out"] = True
            meta["collector_stderr_tail"] = f"timed out after {effective_timeout}s"
            meta["collector_stdout_tail"] = (
                exc.stdout if isinstance(exc.stdout, str) else ""
            )[-2000:]
    else:
        import sys

        local_argv = [
            sys.executable,
            "-m",
            "featureliftbench.exec_contract.instrument",
            "--trace",
            "--repo",
            str(repo),
            "--out",
            str(runtime),
        ]
        for prefix in watch:
            local_argv.extend(["--watch", prefix])
        for plugin in runtime_plan.get("required_pytest_plugins") or []:
            local_argv.extend(["--plugin", str(plugin)])
        local_argv.append("--")
        local_argv.extend(selected)
        proc = subprocess.run(
            local_argv,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
            timeout=max(1, int(effective_timeout)),
            env={
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            },
        )
        meta["collector_returncode"] = proc.returncode
        meta["collector_stdout_tail"] = (proc.stdout or "")[-8000:]
        meta["collector_stderr_tail"] = (proc.stderr or "")[-8000:]

    report = None
    report_path = runtime / PYTEST_REPORT
    if report_path.is_file():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = None

    events: list[dict[str, Any]] = []
    traces_path = runtime / TRACE_JSONL
    if traces_path.is_file():
        for line in traces_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    useful = [
        e
        for e in events
        if not is_noise_event(e, allow_path_prefixes=watch)
    ]
    meta["trace_events"] = len(events)
    meta["useful_trace_events"] = len(useful)
    meta["pytest_passed"] = None if report is None else report.get("passed")

    if useful and report and report.get("passed"):
        meta["trace_quality"] = "high"
    elif useful and len(useful) >= 5:
        meta["trace_quality"] = "medium"
    elif useful:
        meta["trace_quality"] = "low"
    else:
        meta["trace_quality"] = "low"

    (runtime / COLLECT_META).write_text(dumps_pretty(meta), encoding="utf-8")
    _write_facts(workspace, meta, report=report, events=useful)
    return meta


def _write_facts(
    workspace: Path,
    meta: dict[str, Any],
    *,
    report: dict[str, Any] | None,
    events: list[dict[str, Any]],
) -> None:
    lines: list[str] = [
        "# Runtime Facts (Execution-Guided Contract)",
        "",
        "These facts were recorded by running **upstream repository tests** under",
        "instrumentation. They are ground-truth observations from `repo/`, not",
        "model-invented probes. Prefer them over speculation.",
        "",
        f"- Trace quality: `{meta.get('trace_quality')}`",
        f"- Selected tests: {len(meta.get('selected_tests') or [])}",
        f"- Trace events (useful): {meta.get('useful_trace_events', len(events))}",
        f"- Upstream pytest passed: `{meta.get('pytest_passed')}`",
        "",
        "## Selected upstream tests",
        "",
    ]
    for rel in meta.get("selected_tests") or []:
        lines.append(f"- `{rel}`")
    if not meta.get("selected_tests"):
        lines.append("- _(none selected)_")

    env_keys: list[str] = []
    if report and isinstance(report.get("env_keys_read"), list):
        env_keys = list(report["env_keys_read"])
    lines.extend(["", "## Environment keys read during upstream runs", ""])
    if env_keys:
        for key in env_keys[:40]:
            lines.append(f"- `{key}`")
    else:
        lines.append("- _(none recorded)_")

    lines.extend(["", "## Sample observed calls / exceptions", ""])
    interesting = [e for e in events if e.get("exception")][:15]
    interesting += [e for e in events if not e.get("exception")][:25]
    seen = 0
    for event in interesting:
        if seen >= 30:
            break
        seen += 1
        func = event.get("func")
        if event.get("exception"):
            exc = event["exception"]
            lines.append(
                f"- `{func}` raised `{exc.get('type')}`: {exc.get('message')}"
            )
        else:
            lines.append(
                f"- `{func}` args=`{json.dumps(event.get('args'), ensure_ascii=False)[:180]}` "
                f"return=`{json.dumps(event.get('return'), ensure_ascii=False)[:120]}`"
            )
    if seen == 0:
        lines.append("- _(no useful events)_")
        lines.append(
            "- Phase 0 produced no admissible dynamic evidence. The fail-closed "
            "method must not expose this capsule to the implementation agent."
        )

    lines.extend(
        [
            "",
            "## Required submission API (from TASK public_spec)",
            "",
        ]
    )
    for item in meta.get("required_api") or []:
        lines.append(f"- `{item.get('path')}` ({item.get('kind')})")

    lines.extend(
        [
            "",
            "## Instructions",
            "",
            "1. Implement `submission/featurelifted/` to match TASK **and** these facts.",
            "2. Make `PYTHONPATH=submission pytest contracts/ -q` pass before finishing "
            "(behavior scenarios must run for real — hasattr-only is not enough).",
            "3. Do **not** weaken or delete contracts to force a green run.",
            "4. Prefer upstream source under `repo/` over speculation when facts are thin, "
            "but TASK `public_spec` signatures win when they disagree with upstream call shapes.",
            "5. Symbolic ids from TASK (e.g. head/base) must work through `get_revision`, "
            "not only through `get_revisions` / `get_current_head`.",
            "",
        ]
    )
    (workspace / FACTS_FILE).write_text("\n".join(lines), encoding="utf-8")
