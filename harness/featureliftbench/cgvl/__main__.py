"""Dump a CGVL matrix for a task directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..metadata import load_metadata
from .expand import build_cgvl_matrix
from .expand import required_cells


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m featureliftbench.cgvl")
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    metadata = load_metadata(args.task_dir).data
    public_spec = metadata.get("public_spec")
    if not isinstance(public_spec, dict) or not public_spec:
        print("task has no metadata.public_spec", file=sys.stderr)
        return 2
    matrix = build_cgvl_matrix(public_spec)
    if args.json:
        print(json.dumps(matrix, indent=2, sort_keys=True))
        return 0
    cells = matrix.get("cells") or []
    required = required_cells(matrix)
    print(f"{args.task_dir.name}: {len(cells)} cells, {len(required)} required")
    for cell in cells:
        flag = "U" if cell.get("undetermined") else ("R" if cell.get("required") else " ")
        print(
            f"  [{flag}] {cell.get('id')}  {cell.get('role')}  "
            f"{cell.get('public_entry')}  {cell.get('input_variant') or ''}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
