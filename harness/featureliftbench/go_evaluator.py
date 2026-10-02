"""Go evaluator for FeatureLiftBench v2 pilot tasks."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evaluator import CommandResult
from .evaluator import _command_result_payload
from .evaluator import _run_command
from .evaluator import _skipped_command_result
from .evaluator import _write_command_logs
from .metadata import load_metadata
from .metrics import count_files
from .metrics import count_go_loc
from .metrics import directory_size_bytes
from .scoring import score_submission
from .validate import validate_task


@dataclass(frozen=True)
class GoModInfo:
    module: str
    requires: tuple[str, ...]
    replaces: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class GoStaticCheck:
    module_path: str
    imports: tuple[str, ...]
    requires: tuple[str, ...]
    replaces: tuple[tuple[str, str], ...]
    import_issues: tuple[str, ...]
    module_issues: tuple[str, ...]
    structural_issues: tuple[str, ...]


def evaluate_go_submission(
    task_dir: str | Path,
    submission_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Evaluate a Go submission and write ``result.json`` under ``output_dir``."""

    task_path = Path(task_dir).resolve()
    submission_path = Path(submission_dir).resolve()
    output_path = Path(output_dir).resolve()
    logs_path = output_path / "logs"
    output_path.mkdir(parents=True, exist_ok=True)
    logs_path.mkdir(parents=True, exist_ok=True)

    validation = validate_task(task_path)
    errors: list[str] = []
    if not validation.valid:
        errors.extend(f"invalid task: {error}" for error in validation.errors)

    metadata: dict[str, Any] = {}
    try:
        metadata = load_metadata(task_path).data
    except Exception as exc:
        if not errors:
            errors.append(f"cannot load metadata: {exc}")

    task_id = metadata.get("task_id", validation.task_id or task_path.name)
    if not isinstance(task_id, str) or not task_id:
        task_id = task_path.name
    submission_name = submission_path.name
    source_repo = task_path / "repo"

    if not submission_path.exists():
        errors.append(f"submission dir not found: {submission_path}")
    elif not submission_path.is_dir():
        errors.append(f"submission path is not a directory: {submission_path}")

    metrics = _collect_go_metrics(submission_path, source_repo=source_repo)
    expected_module = _expected_module(metadata, task_id)
    forbidden_imports = _load_forbidden_imports(task_path, metadata)
    forbidden_modules = _load_forbidden_modules(task_path, metadata)
    allowed_modules = _load_allowed_modules(task_path, metadata)

    static_check = (
        _static_check_submission(
            submission_path=submission_path,
            expected_module=expected_module,
            forbidden_imports=forbidden_imports,
            forbidden_modules=forbidden_modules,
            allowed_modules=allowed_modules,
        )
        if submission_path.exists() and submission_path.is_dir()
        else GoStaticCheck("", (), (), (), (), (), ())
    )
    errors.extend(static_check.import_issues)
    errors.extend(static_check.module_issues)
    errors.extend(static_check.structural_issues)

    original_import_pass = not static_check.import_issues
    forbidden_module_pass = not static_check.module_issues
    offline_dependency_pass = False
    build_pass = False
    test_pass = False
    race_pass: bool | None = None
    stress_pass: bool | None = None
    resolved_modules: list[str] = []

    environment_info: dict[str, str] = {
        "go": "",
        "runtime_submission_dir": "",
    }
    dependency_install_result = _skipped_command_result("Go pilot tasks do not install dependencies")
    submission_install_result = _skipped_command_result("Go submissions are evaluated in-place")
    eval_tooling_result: CommandResult | None = None
    offline_dependency_result: CommandResult | None = None
    build_result: CommandResult | None = None
    public_result: CommandResult | None = None
    hidden_result: CommandResult | None = None
    race_result: CommandResult | None = None

    can_run = (
        validation.valid
        and submission_path.exists()
        and submission_path.is_dir()
        and not static_check.structural_issues
        and original_import_pass
        and forbidden_module_pass
    )

    if can_run:
        timeout_seconds = _timeout_seconds(metadata)
        go_binary = shutil.which("go")
        if go_binary is None:
            eval_tooling_result = CommandResult(
                returncode=127,
                duration_seconds=0.0,
                stdout="",
                stderr="go executable not found",
                reason="go executable not found",
            )
            errors.append("go executable not found")
        else:
            env = _go_env()
            with tempfile.TemporaryDirectory(prefix="featureliftbench-go-eval-") as tmp:
                run_cwd = Path(tmp)
                runtime_submission_path = run_cwd / "submission-runtime"
                environment_info["runtime_submission_dir"] = str(runtime_submission_path)

                try:
                    shutil.copytree(submission_path, runtime_submission_path, symlinks=True)
                except OSError as exc:
                    errors.append(f"submission runtime copy failed: {exc}")
                    runtime_submission_path.mkdir(parents=True, exist_ok=True)

                eval_tooling_result = _run_go_command(
                    ["go", "version"],
                    cwd=runtime_submission_path,
                    env=env,
                    timeout_seconds=timeout_seconds,
                )
                environment_info["go"] = (eval_tooling_result.stdout or "").strip()
                _write_command_logs(logs_path, "eval_tooling", eval_tooling_result)

                if eval_tooling_result.passed:
                    offline_dependency_result = _run_go_command(
                        ["go", "list", "-deps", "-json", "./..."],
                        cwd=runtime_submission_path,
                        env=env,
                        timeout_seconds=timeout_seconds,
                    )
                    _write_command_logs(logs_path, "offline_dependency", offline_dependency_result)
                    if offline_dependency_result.passed:
                        resolved_modules = _resolved_modules_from_go_list(offline_dependency_result.stdout)
                        resolved_issues = _forbidden_resolved_module_issues(
                            resolved_modules,
                            forbidden_modules,
                        )
                        if resolved_issues:
                            errors.extend(resolved_issues)
                            forbidden_module_pass = False
                        else:
                            offline_dependency_pass = True
                    else:
                        errors.append("offline dependency probe failed")

                if eval_tooling_result.passed and offline_dependency_pass and forbidden_module_pass:
                    build_result = _run_go_command(
                        ["go", "test", "./...", "-run", "^$", "-count=1", f"-timeout={timeout_seconds}s"],
                        cwd=runtime_submission_path,
                        env=env,
                        timeout_seconds=timeout_seconds,
                    )
                    _write_command_logs(logs_path, "build", build_result)
                    build_pass = build_result.passed

                if build_pass:
                    public_runtime = run_cwd / "public-runtime"
                    hidden_runtime = run_cwd / "hidden-runtime"
                    _copy_runtime_with_tests(
                        runtime_submission_path,
                        task_path / _test_path(metadata, "public", "public_tests/"),
                        public_runtime,
                        prefix="public",
                    )
                    public_result = _run_go_command(
                        ["go", "test", "./...", "-count=1", f"-timeout={timeout_seconds}s"],
                        cwd=public_runtime,
                        env=env,
                        timeout_seconds=timeout_seconds,
                    )
                    _write_command_logs(logs_path, "public", public_result)

                    _copy_runtime_with_tests(
                        runtime_submission_path,
                        task_path / _test_path(metadata, "hidden", "hidden_tests/"),
                        hidden_runtime,
                        prefix="hidden",
                    )
                    hidden_result = _run_go_command(
                        ["go", "test", "./...", "-count=1", f"-timeout={timeout_seconds}s"],
                        cwd=hidden_runtime,
                        env=env,
                        timeout_seconds=timeout_seconds,
                    )
                    _write_command_logs(logs_path, "hidden", hidden_result)
                    test_pass = public_result.passed and hidden_result.passed

                    if _race_required(metadata):
                        race_result = _run_go_command(
                            ["go", "test", "./...", "-race", "-count=1", "-timeout=120s"],
                            cwd=hidden_runtime,
                            env={**env, "CGO_ENABLED": "1"},
                            timeout_seconds=max(120, timeout_seconds),
                        )
                        _write_command_logs(logs_path, "race", race_result)
                        race_pass = race_result.passed
                    else:
                        race_pass = None

    if eval_tooling_result is not None:
        _write_command_logs(logs_path, "eval_tooling", eval_tooling_result)
    if dependency_install_result is not None:
        _write_command_logs(logs_path, "dependency_install", dependency_install_result)
    if submission_install_result is not None:
        _write_command_logs(logs_path, "submission_install", submission_install_result)

    race_gate_pass = True if race_pass is None else race_pass
    gate = (
        1.0
        if (
            build_pass
            and test_pass
            and original_import_pass
            and forbidden_module_pass
            and offline_dependency_pass
            and race_gate_pass
        )
        else 0.0
    )
    scores = score_submission(
        metrics=metrics,
        metadata=metadata,
        functional_gate_score=gate,
    )

    result: dict[str, Any] = {
        "task_id": task_id,
        "submission": submission_name,
        "status": "passed" if gate else "failed",
        "build_pass": build_pass,
        "test_pass": test_pass,
        "original_import_pass": original_import_pass,
        "forbidden_module_pass": forbidden_module_pass,
        "offline_dependency_pass": offline_dependency_pass,
        "race_pass": race_pass,
        "stress_pass": stress_pass,
        "environment": environment_info,
        "dependency_install": _command_result_payload(dependency_install_result),
        "eval_tooling": _command_result_payload(eval_tooling_result),
        "submission_install": _command_result_payload(submission_install_result),
        "offline_dependency": _command_result_payload(offline_dependency_result),
        "build": _command_result_payload(build_result),
        "public_tests": _command_result_payload(public_result),
        "hidden_tests": _command_result_payload(hidden_result),
        "race_tests": _command_result_payload(race_result),
        "metrics": metrics,
        "scores": scores,
        "go": {
            "module_path": static_check.module_path,
            "source_go_loc": metrics["source_loc"],
            "submission_go_loc": metrics["loc"],
            "forbidden_imports": forbidden_imports,
            "forbidden_modules": forbidden_modules,
            "resolved_modules": sorted(resolved_modules),
        },
        "logs": {
            "dir": str(logs_path),
        },
        "errors": errors,
    }

    result_path = output_path / "result.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _collect_go_metrics(submission_path: Path, *, source_repo: Path) -> dict[str, int]:
    source_loc = count_go_loc(source_repo) if source_repo.exists() else 0
    if not submission_path.exists() or not submission_path.is_dir():
        return {
            "file_count": 0,
            "loc": 0,
            "source_loc": source_loc,
            "package_bytes": 0,
            "dependency_count": 0,
            "suspicious_file_count": 0,
        }

    return {
        "file_count": count_files(submission_path),
        "loc": count_go_loc(submission_path),
        "source_loc": source_loc,
        "package_bytes": directory_size_bytes(submission_path),
        "dependency_count": len(_parse_go_mod(submission_path / "go.mod").requires)
        if (submission_path / "go.mod").is_file()
        else 0,
        "suspicious_file_count": 0,
    }


def _static_check_submission(
    *,
    submission_path: Path,
    expected_module: str,
    forbidden_imports: list[str],
    forbidden_modules: list[str],
    allowed_modules: list[str],
) -> GoStaticCheck:
    import_issues: list[str] = []
    module_issues: list[str] = []
    structural_issues: list[str] = []

    go_mod_path = submission_path / "go.mod"
    if not go_mod_path.is_file():
        structural_issues.append("missing required file: go.mod")
        go_mod = GoModInfo("", (), ())
    else:
        go_mod = _parse_go_mod(go_mod_path)

    if go_mod.module != expected_module:
        structural_issues.append(
            f"go.mod module must be {expected_module}, got {go_mod.module or '<missing>'}"
        )

    if (submission_path / "go.work").exists():
        structural_issues.append("go.work is not allowed in submissions")

    structural_issues.extend(_symlink_escape_issues(submission_path))

    imports = _find_go_imports(submission_path)
    for import_path in imports:
        match = _matching_forbidden(import_path, forbidden_imports)
        if match:
            import_issues.append(f"imports forbidden Go package {import_path!r} (matched {match!r})")

    allowed = {_normalize_module(item) for item in allowed_modules}
    for module in go_mod.requires:
        match = _matching_forbidden(module, forbidden_modules)
        if match:
            module_issues.append(f"requires forbidden Go module {module!r} (matched {match!r})")
        elif module and _normalize_module(module) not in allowed:
            module_issues.append(f"requires Go module not listed in allowed_modules: {module}")

    for old, new in go_mod.replaces:
        old_match = _matching_forbidden(old, forbidden_modules)
        new_match = _matching_forbidden(new, forbidden_modules)
        if old_match:
            module_issues.append(f"replaces forbidden Go module {old!r} (matched {old_match!r})")
        if new_match:
            module_issues.append(f"replace target uses forbidden Go module {new!r} (matched {new_match!r})")
        if _replace_target_is_host_path(new):
            module_issues.append(f"replace target must not point at a local or host path: {new}")

    vendor_modules = submission_path / "vendor" / "modules.txt"
    if vendor_modules.is_file():
        text = vendor_modules.read_text(encoding="utf-8", errors="ignore")
        for forbidden in forbidden_modules:
            if forbidden and forbidden in text:
                module_issues.append(f"vendor/modules.txt references forbidden Go module {forbidden!r}")

    return GoStaticCheck(
        module_path=go_mod.module,
        imports=tuple(sorted(imports)),
        requires=go_mod.requires,
        replaces=go_mod.replaces,
        import_issues=tuple(import_issues),
        module_issues=tuple(module_issues),
        structural_issues=tuple(structural_issues),
    )


def _parse_go_mod(path: Path) -> GoModInfo:
    if not path.is_file():
        return GoModInfo("", (), ())
    module = ""
    requires: list[str] = []
    replaces: list[tuple[str, str]] = []
    block: str | None = None
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line == ")":
            block = None
            continue
        if line.startswith("module "):
            module = line.split(None, 1)[1].strip()
            continue
        if line == "require (":
            block = "require"
            continue
        if line == "replace (":
            block = "replace"
            continue
        if line.startswith("require "):
            requirement = _first_token(line.removeprefix("require ").strip())
            if requirement:
                requires.append(requirement)
            continue
        if line.startswith("replace "):
            parsed = _parse_replace(line.removeprefix("replace ").strip())
            if parsed is not None:
                replaces.append(parsed)
            continue
        if block == "require":
            requirement = _first_token(line)
            if requirement:
                requires.append(requirement)
        elif block == "replace":
            parsed = _parse_replace(line)
            if parsed is not None:
                replaces.append(parsed)
    return GoModInfo(module=module, requires=tuple(requires), replaces=tuple(replaces))


def _parse_replace(line: str) -> tuple[str, str] | None:
    if "=>" not in line:
        return None
    left, right = line.split("=>", 1)
    old = _first_token(left.strip())
    new = _first_token(right.strip())
    if not old or not new:
        return None
    return old, new


def _find_go_imports(root: Path) -> set[str]:
    imports: set[str] = set()
    for path in root.rglob("*.go"):
        if not path.is_file() or "vendor" in path.relative_to(root).parts:
            continue
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        in_block = False
        for raw_line in lines:
            line = raw_line.strip()
            if in_block:
                if line == ")":
                    in_block = False
                    continue
                match = re.match(r'^(?:[._A-Za-z0-9]+\s+)?\"([^\"]+)\"', line)
                if match:
                    imports.add(match.group(1))
                continue
            if line.startswith("import ("):
                in_block = True
                continue
            match = re.match(r'^import\s+(?:[._A-Za-z0-9]+\s+)?\"([^\"]+)\"', line)
            if match:
                imports.add(match.group(1))
    return imports


def _copy_runtime_with_tests(base_runtime: Path, test_dir: Path, target_runtime: Path, *, prefix: str) -> None:
    shutil.copytree(base_runtime, target_runtime, symlinks=True)
    if not test_dir.exists():
        return
    target_test_dir = target_runtime / f"flb_{prefix}_tests"
    target_test_dir.mkdir(parents=True, exist_ok=True)
    for index, test_file in enumerate(sorted(test_dir.rglob("*_test.go"))):
        if not test_file.is_file():
            continue
        target = target_test_dir / f"{index}_{test_file.name}"
        shutil.copy2(test_file, target)


def _run_go_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> CommandResult:
    try:
        return _run_command(command, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
    except FileNotFoundError as exc:
        return CommandResult(
            returncode=127,
            duration_seconds=0.0,
            stdout="",
            stderr=str(exc),
            reason="go executable not found",
        )


def _go_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GOWORK": "off",
            "GOPROXY": "off",
            "GONOSUMDB": "*",
            "GOFLAGS": "-mod=mod",
            "CGO_ENABLED": "0",
            "GOMAXPROCS": "2",
            "HOME": "/tmp/featureliftbench-home",
            "GOCACHE": "/tmp/featureliftbench-go-build",
            "GOMODCACHE": "/tmp/featureliftbench-go-mod",
            "TMPDIR": "/tmp",
        }
    )
    return env


def _resolved_modules_from_go_list(stdout: str | bytes | None) -> list[str]:
    text = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else (stdout or "")
    decoder = json.JSONDecoder()
    index = 0
    modules: set[str] = set()
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        try:
            item, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            break
        if isinstance(item, dict):
            module = item.get("Module")
            if isinstance(module, dict):
                path = module.get("Path")
                if isinstance(path, str) and path:
                    modules.add(path)
    return sorted(modules)


def _forbidden_resolved_module_issues(
    resolved_modules: list[str],
    forbidden_modules: list[str],
) -> list[str]:
    issues: list[str] = []
    for module in resolved_modules:
        match = _matching_forbidden(module, forbidden_modules)
        if match:
            issues.append(f"go list resolved forbidden Go module {module!r} (matched {match!r})")
    return issues


def _load_forbidden_imports(task_path: Path, metadata: dict[str, Any]) -> list[str]:
    names = _read_lines(task_path / "evaluation" / "forbidden_imports.txt")
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        names.extend(item for item in environment.get("forbidden_imports", []) if isinstance(item, str))
    source = metadata.get("source")
    if isinstance(source, dict) and isinstance(source.get("module_path"), str):
        names.append(source["module_path"])
    return _dedupe_nonempty(names)


def _load_forbidden_modules(task_path: Path, metadata: dict[str, Any]) -> list[str]:
    names = _read_lines(task_path / "evaluation" / "forbidden_modules.txt")
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        names.extend(item for item in environment.get("forbidden_modules", []) if isinstance(item, str))
    source = metadata.get("source")
    if isinstance(source, dict) and isinstance(source.get("module_path"), str):
        names.append(source["module_path"])
    return _dedupe_nonempty(names)


def _load_allowed_modules(task_path: Path, metadata: dict[str, Any]) -> list[str]:
    names = _read_lines(task_path / "evaluation" / "allowed_modules.txt")
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        names.extend(item for item in environment.get("allowed_modules", []) if isinstance(item, str))
    return _dedupe_nonempty(names)


def _read_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _dedupe_nonempty(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        value = item.strip().rstrip("/")
        if value and value not in result:
            result.append(value)
    return result


def _expected_module(metadata: dict[str, Any], task_id: str) -> str:
    output = metadata.get("output")
    if isinstance(output, dict) and isinstance(output.get("module"), str) and output["module"].strip():
        return output["module"].strip()
    return f"featurelifted.local/{task_id}"


def _timeout_seconds(metadata: dict[str, Any]) -> int:
    environment = metadata.get("environment")
    if isinstance(environment, dict):
        raw = environment.get("timeout_seconds")
        if isinstance(raw, int) and raw > 0:
            return raw
    return 30


def _test_path(metadata: dict[str, Any], key: str, default: str) -> str:
    tests = metadata.get("tests")
    if isinstance(tests, dict):
        value = tests.get(key)
        if isinstance(value, str) and value:
            return value
    return default


def _race_required(metadata: dict[str, Any]) -> bool:
    concurrency = metadata.get("concurrency")
    return isinstance(concurrency, dict) and concurrency.get("race_test") is True


def _first_token(text: str) -> str:
    parts = text.split()
    return parts[0].strip() if parts else ""


def _matching_forbidden(value: str, forbidden_values: list[str]) -> str:
    normalized = value.strip().rstrip("/")
    for forbidden in forbidden_values:
        candidate = forbidden.strip().rstrip("/")
        if candidate and (normalized == candidate or normalized.startswith(candidate + "/")):
            return candidate
    return ""


def _normalize_module(value: str) -> str:
    return value.strip().rstrip("/").lower()


def _replace_target_is_host_path(value: str) -> bool:
    return value.startswith(("/", "./", "../")) or "/../" in value or value == "." or value == ".."


def _symlink_escape_issues(root: Path) -> list[str]:
    issues: list[str] = []
    root_resolved = root.resolve()
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            target = path.resolve()
            target.relative_to(root_resolved)
        except (OSError, ValueError):
            issues.append(f"symlink escapes submission root: {path.relative_to(root)}")
    return issues
