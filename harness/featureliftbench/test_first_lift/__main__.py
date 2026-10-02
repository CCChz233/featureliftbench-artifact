"""python -m featureliftbench.test_first_lift freeze|verify"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .freeze import freeze_characterization
from .freeze import verify_characterization


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("usage: python -m featureliftbench.test_first_lift freeze|verify [--workspace DIR]")
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
