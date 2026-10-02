"""Workspace install + prompt appendix for Test-First Lift."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import CHARACTERIZATION_DIR
from .common import LOCK_FILE
from .common import MAX_CASES
from .common import ORACLE_FILE
from .common import WRAPPER_NAME


_README = f"""# Characterization cases (Test-First Lift)

Write up to {MAX_CASES} Python cases in this directory.

Each case file must define:

```python
CASE_ID = "short-id"
TASK_CLAUSE = "B001 or a public TASK clause summary"
REQUIRED_API = ["featurelifted.SomeAPI"]

def run_upstream():
    # Construct and exercise the ORIGINAL repo behavior.
    return {{"result": ..., "exception": None, "state_after": ...}}

def run_featurelifted():
    # Rebuild the same scenario via the TASK Required API.
    return {{"result": ..., "exception": None, "state_after": ...}}
```

Rules:
- Do NOT hard-code expected answers. The harness records upstream observations.
- Prefer stable JSON fields. Do not compare exception messages.
- After cases are ready, run `./{WRAPPER_NAME} freeze` from the workspace root.
- Only after freeze succeeds, implement `submission/featurelifted/`.
- Then run `./{WRAPPER_NAME} verify`.
"""


_WRAPPER = """#!/usr/bin/env python3
\"\"\"Workspace wrapper for Test-First Lift freeze/verify.\"\"\"

from __future__ import annotations

import json
import sys
from pathlib import Path

# Prefer the mounted FeatureLiftBench harness inside agent Docker.
CANDIDATES = [
    Path("/flb/harness"),
    Path(__file__).resolve().parents[2] / "harness",
    Path(__file__).resolve().parents[1],
]
for candidate in CANDIDATES:
    if (candidate / "featureliftbench").is_dir():
        sys.path.insert(0, str(candidate))
        break

from featureliftbench.test_first_lift.freeze import freeze_characterization  # noqa: E402
from featureliftbench.test_first_lift.freeze import verify_characterization  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("usage: flb-test-first freeze|verify [--workspace DIR]")
        return 2
    command = args[0]
    workspace = Path.cwd()
    if "--workspace" in args:
        idx = args.index("--workspace")
        workspace = Path(args[idx + 1]).resolve()
    if command == "freeze":
        result = freeze_characterization(workspace)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1
    if command == "verify":
        result = verify_characterization(workspace)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
"""


def install_test_first_lift_workspace(
    workspace_dir: str | Path,
    *,
    required_api_paths: list[str] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_dir).resolve()
    char_dir = workspace / CHARACTERIZATION_DIR
    char_dir.mkdir(parents=True, exist_ok=True)
    (char_dir / "README.md").write_text(_README, encoding="utf-8")
    if required_api_paths is not None:
        payload = {
            "schema_version": "featureliftbench.test_first_lift_required_api.v1",
            "required_api": sorted(set(required_api_paths)),
        }
        (char_dir / "REQUIRED_API.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    wrapper = workspace / WRAPPER_NAME
    wrapper.write_text(_WRAPPER, encoding="utf-8")
    wrapper.chmod(0o755)
    (workspace / "submission").mkdir(exist_ok=True)
    return {
        "test_first_lift": True,
        "characterization_dir": CHARACTERIZATION_DIR,
        "wrapper": WRAPPER_NAME,
        "oracle_file": ORACLE_FILE,
        "lock_file": LOCK_FILE,
        "required_api_count": len(required_api_paths or []),
    }


def task_appendix() -> str:
    return (
        "## Test-First Lift protocol\n\n"
        "This is a **single continuous agent run** with two stages.\n\n"
        "### Stage A — characterize the original repo\n"
        f"- Explore `repo/` and write up to {MAX_CASES} cases under "
        f"`{CHARACTERIZATION_DIR}/`.\n"
        "- Each case must define `CASE_ID`, `TASK_CLAUSE`, `REQUIRED_API`, "
        "`run_upstream()`, and `run_featurelifted()`.\n"
        "- `run_upstream()` exercises the original repository.\n"
        "- `run_featurelifted()` rebuilds the same scenario via the TASK "
        "Required API (no expected constants).\n"
        "- Cover every Required API path in some case's `REQUIRED_API` list.\n"
        f"- When ready, run `./{WRAPPER_NAME} freeze` from the workspace root.\n"
        "- Freeze runs upstream twice in independent processes, writes "
        f"`{ORACLE_FILE}`, checks that an empty package fails, and locks "
        f"`{CHARACTERIZATION_DIR}/`.\n\n"
        "### Stage B — implement the lifted package\n"
        f"- Only after freeze succeeds, implement `submission/featurelifted/`.\n"
        f"- Do **not** modify `{CHARACTERIZATION_DIR}/`, `{ORACLE_FILE}`, or "
        f"`{LOCK_FILE}`.\n"
        f"- Use `./{WRAPPER_NAME} verify` to compare against the frozen oracle.\n"
        "- When done, leave a working submission package.\n\n"
        "Formal public/hidden evaluator tests remain invisible; they run after "
        "you finish.\n"
    )


def openhands_appendix() -> str:
    return task_appendix()
