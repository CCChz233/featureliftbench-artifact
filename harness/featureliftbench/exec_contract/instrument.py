"""In-process pytest + sys.settrace collector (runs inside agent Docker)."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


def _project(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return "<max_depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 200 else value[:200] + "…"
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, (list, tuple)):
        items = list(value)[:20]
        out = [_project(v, depth + 1) for v in items]
        if len(value) > 20:
            out.append("…")
        return out
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= 20:
                out["…"] = f"+{len(value) - 20}"
                break
            out[str(k)[:80]] = _project(v, depth + 1)
        return out
    text = repr(value)
    return {"__type__": type(value).__name__, "__repr__": text[:120] + ("…" if len(text) > 120 else "")}


class _EnvWatch:
    def __init__(self) -> None:
        self.keys: set[str] = set()
        self._orig_getitem = os.environ.__getitem__
        self._orig_get = os.environ.get

    def install(self) -> None:
        watch = self

        def getitem(key: str) -> str:  # type: ignore[override]
            watch.keys.add(str(key))
            return watch._orig_getitem(key)

        def get(key: str, default: Any = None) -> Any:  # type: ignore[override]
            watch.keys.add(str(key))
            return watch._orig_get(key, default)

        os.environ.__getitem__ = getitem  # type: ignore[method-assign]
        os.environ.get = get  # type: ignore[method-assign]

    def uninstall(self) -> None:
        os.environ.__getitem__ = self._orig_getitem  # type: ignore[method-assign]
        os.environ.get = self._orig_get  # type: ignore[method-assign]


_NOISE_PATH_MARKERS = (
    "/_pytest/",
    "/pytest/",
    "/pluggy/",
    "/site-packages/_pytest/",
    "/site-packages/pluggy/",
    "/site-packages/py.py",
)
_HARD_NOISE_PATH_MARKERS = (
    "/_vendor/",
    "/vendor/",
)


class _CallTracer:
    def __init__(self, watch_prefixes: list[str], max_events: int = 5000) -> None:
        self.watch_prefixes = tuple(p for p in watch_prefixes if "/" in p)
        self.max_events = max_events
        self.events: list[dict[str, Any]] = []
        self._stack: dict[int, dict[str, Any]] = {}

    def _interesting(self, filename: str) -> bool:
        norm = filename.replace("\\", "/")
        if any(m in norm for m in _HARD_NOISE_PATH_MARKERS):
            return False
        if self.watch_prefixes:
            # Explicit scope wins. Pytest tasks intentionally watch /_pytest/;
            # the old noise-first ordering made those traces impossible.
            return any(p in norm for p in self.watch_prefixes)
        if any(m in norm for m in _NOISE_PATH_MARKERS):
            return False
        return "/repo/" in norm and "/tests/" not in norm

    def __call__(self, frame, event, arg):  # noqa: ANN001
        if len(self.events) >= self.max_events:
            return None
        code = frame.f_code
        if (
            code.co_name.startswith("__")
            and code.co_name.endswith("__")
            and code.co_name != "__init__"
        ):
            return self
        if code.co_argcount == 0 and code.co_name[:1].isupper():
            # Python traces execution of a class body as a call whose code name
            # is the class name. It is not a runtime constructor observation.
            return self
        filename = code.co_filename
        if not self._interesting(filename):
            return self
        if event == "call":
            args: dict[str, Any] = {}
            owner = None
            try:
                local = frame.f_locals
                if "self" in local:
                    owner = type(local["self"]).__name__
                elif isinstance(local.get("cls"), type):
                    owner = local["cls"].__name__
                for name in code.co_varnames[: code.co_argcount]:
                    if name in {"self", "cls"}:
                        continue
                    if name in local:
                        args[name] = _project(local[name])
            except Exception:  # noqa: BLE001
                args = {"__error__": "locals_unreadable"}
            self._stack[id(frame)] = {
                "qualname": f"{code.co_filename}::{code.co_name}",
                "func": code.co_name,
                "file": filename,
                "args": args,
            }
            if owner:
                self._stack[id(frame)]["owner"] = owner
            return self
        if event == "return" and id(frame) in self._stack:
            base = self._stack.pop(id(frame))
            base["return"] = _project(arg)
            base["event"] = "call"
            self.events.append(base)
            return self
        if event == "exception" and id(frame) in self._stack:
            base = self._stack.pop(id(frame))
            exc_type = arg[0]
            exc = arg[1]
            base["exception"] = {
                "type": getattr(exc_type, "__name__", str(exc_type)),
                "message": str(exc)[:300],
            }
            base["event"] = "exception"
            self.events.append(base)
            return self
        return self


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Usage:
    #   python -m featureliftbench.exec_contract.instrument \
    #     --repo /flb/workspace/repo \
    #     --out /flb/workspace/runtime_traces \
    #     --watch pkg1 --watch pkg2 \
    #     -- tests/test_a.py tests/test_b.py
    repo = Path(".")
    out = Path("runtime_traces")
    watch: list[str] = []
    plugins: list[str] = []
    tests: list[str] = []
    enable_trace = True
    if "--" in argv:
        cut = argv.index("--")
        opts, tests = argv[:cut], argv[cut + 1 :]
    else:
        opts, tests = argv, []
    i = 0
    while i < len(opts):
        if opts[i] == "--repo" and i + 1 < len(opts):
            repo = Path(opts[i + 1])
            i += 2
        elif opts[i] == "--out" and i + 1 < len(opts):
            out = Path(opts[i + 1])
            i += 2
        elif opts[i] == "--watch" and i + 1 < len(opts):
            watch.append(opts[i + 1])
            i += 2
        elif opts[i] == "--plugin" and i + 1 < len(opts):
            plugins.append(opts[i + 1])
            i += 2
        elif opts[i] == "--no-trace":
            enable_trace = False
            i += 1
        elif opts[i] == "--trace":
            enable_trace = True
            i += 1
        else:
            i += 1

    out.mkdir(parents=True, exist_ok=True)
    # Import pytest before enabling tracing. Otherwise package-under-test tasks
    # such as pytest itself exhaust the event budget on import-time framework
    # initialization before a selected test executes.
    import pytest  # noqa: WPS433

    env_watch = _EnvWatch()
    tracer = _CallTracer(watch_prefixes=watch)
    env_watch.install()
    if enable_trace:
        sys.settrace(tracer)

    report: dict[str, Any] = {
        "repo": str(repo),
        "tests": tests,
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
        "passed": None,
        "trace_enabled": enable_trace,
    }
    try:
        os.chdir(str(repo))
        plugin_args: list[str] = []
        for plugin in plugins:
            plugin_args.extend(["-p", plugin])
        os.environ.pop("PYTEST_ADDOPTS", None)
        code = pytest.main(
            [
                "-q",
                "--tb=line",
                "-o",
                "addopts=",
                *plugin_args,
                "-p",
                "no:cacheprovider",
                "--maxfail=15",
                *tests,
            ]
        )
        report["returncode"] = int(code)
        report["passed"] = int(code) == 0
    except SystemExit as exc:
        report["returncode"] = int(exc.code or 0)
        report["passed"] = report["returncode"] == 0
    except Exception as exc:  # noqa: BLE001
        report["returncode"] = 1
        report["passed"] = False
        report["stderr_tail"] = traceback.format_exc()[-2000:]
        report["error"] = str(exc)
    finally:
        if enable_trace:
            sys.settrace(None)
        env_watch.uninstall()

    traces_path = out / "traces.jsonl"
    with traces_path.open("w", encoding="utf-8") as handle:
        for event in tracer.events:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    report["trace_events"] = len(tracer.events)
    report["env_keys_read"] = sorted(env_watch.keys)
    (out / "pytest_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
