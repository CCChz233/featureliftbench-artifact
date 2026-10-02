"""Isolated import and reflection probe used by the closure checker."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import sys
import types
from pathlib import Path
from typing import Any


class ResolutionFailure(LookupError):
    """A probe failure with a machine-readable origin."""

    def __init__(self, message: str, *, error_kind: str) -> None:
        super().__init__(message)
        self.error_kind = error_kind


def _resolve(path: str) -> tuple[Any, str | None]:
    parts = path.split(".")
    imported = None
    consumed = 0
    import_error = ""
    import_error_kind = "missing_api"
    for index in range(len(parts), 0, -1):
        name = ".".join(parts[:index])
        try:
            imported = importlib.import_module(name)
            consumed = index
            break
        except ModuleNotFoundError as exc:
            if exc.name != name and not name.startswith(f"{exc.name}."):
                if exc.name == "featurelifted" or str(exc.name).startswith(
                    "featurelifted."
                ):
                    import_error = f"submission import failed: {exc}"
                    import_error_kind = "submission_import_error"
                else:
                    import_error = f"checker dependency unavailable: {exc}"
                    import_error_kind = "checker_dependency_unavailable"
                break
        except Exception as exc:  # noqa: BLE001 - report import behavior
            import_error = f"import failed: {type(exc).__name__}: {exc}"
            import_error_kind = "submission_import_error"
            break
    if imported is None:
        raise ResolutionFailure(
            import_error or f"cannot import any module prefix of {path}",
            error_kind=import_error_kind,
        )
    current = imported
    for part in parts[consumed:]:
        try:
            current = inspect.getattr_static(current, part)
        except AttributeError as exc:
            # Dynamic proxies and instance-only attributes cannot be safely traversed.
            if not isinstance(current, (types.ModuleType, type)):
                return current, f"dynamic attribute {part!r} cannot be inspected safely"
            raise ResolutionFailure(
                f"missing attribute {part!r} in {path}", error_kind="missing_api"
            ) from exc
    return current, None


def _unwrap(value: Any) -> Any:
    if isinstance(value, (classmethod, staticmethod)):
        return value.__func__
    return value


def _kind_ok(value: Any, kind: str) -> bool:
    value = _unwrap(value)
    normalized = kind.strip().lower()
    if normalized == "module":
        return isinstance(value, types.ModuleType)
    if normalized == "class":
        return isinstance(value, type)
    if normalized == "exception":
        return isinstance(value, type) and issubclass(value, BaseException)
    if normalized in {"function", "method", "classmethod", "staticmethod"}:
        return callable(value)
    if normalized in {"constant", "object", "attribute", "property"}:
        return True
    return True


def _signature(value: Any) -> dict[str, Any]:
    target = _unwrap(value)
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError) as exc:
        return {"available": False, "error": str(exc)}
    parameters = []
    for parameter in signature.parameters.values():
        parameters.append(
            {
                "name": parameter.name,
                "kind": parameter.kind.name,
                "has_default": parameter.default is not inspect.Parameter.empty,
                "default_repr": (
                    None
                    if parameter.default is inspect.Parameter.empty
                    else repr(parameter.default)
                ),
            }
        )
    return {
        "available": True,
        "text": str(signature),
        "parameters": parameters,
    }


def inspect_apis(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for entry in entries:
        path = str(entry.get("path") or "")
        kind = str(entry.get("kind") or "")
        try:
            value, unknown = _resolve(path)
        except ResolutionFailure as exc:
            if (
                kind.strip().lower() in {"attribute", "property"}
                and path.count(".") >= 2
            ):
                results.append(
                    {
                        "path": path,
                        "kind": kind,
                        "status": "unknown",
                        "error_kind": exc.error_kind,
                        "error": (
                            "nested attribute may be instance-only and cannot be "
                            f"inspected safely: {exc}"
                        ),
                    }
                )
                continue
            results.append(
                {
                    "path": path,
                    "kind": kind,
                    "status": (
                        "unknown"
                        if exc.error_kind == "checker_dependency_unavailable"
                        else "fail"
                    ),
                    "error": str(exc),
                    "error_kind": exc.error_kind,
                }
            )
            continue
        if unknown:
            results.append(
                {"path": path, "kind": kind, "status": "unknown", "error": unknown}
            )
            continue
        actual_type = (
            f"{type(_unwrap(value)).__module__}.{type(_unwrap(value)).__name__}"
        )
        if not _kind_ok(value, kind):
            results.append(
                {
                    "path": path,
                    "kind": kind,
                    "status": "fail",
                    "error": f"expected {kind}, got {actual_type}",
                }
            )
            continue
        result = {
            "path": path,
            "kind": kind,
            "status": "pass",
            "actual_type": actual_type,
        }
        if entry.get("signature"):
            result["signature"] = _signature(value)
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--entries", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.submission.resolve()))
    entries = json.loads(args.entries.read_text(encoding="utf-8"))
    print(json.dumps({"results": inspect_apis(entries)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
