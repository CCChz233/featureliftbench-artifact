"""Small deterministic tools used by evidence Agents and audit operators."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .citation_validator import build_citation
from .citation_validator import validate_citation
from .schema import validate_audit_record


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    cite = subparsers.add_parser("cite")
    cite.add_argument("--task-dir", type=Path, required=True)
    cite.add_argument("--path", required=True)
    cite.add_argument(
        "--kind", choices=("task", "public_spec", "repository"), required=True
    )
    cite.add_argument("--start-line", type=int, required=True)
    cite.add_argument("--end-line", type=int, required=True)
    cite.add_argument("--claim", required=True)

    validate = subparsers.add_parser("validate-record")
    validate.add_argument("record", type=Path)
    validate.add_argument("--task-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "cite":
        try:
            citation = build_citation(
                args.task_dir,
                path=args.path,
                kind=args.kind,
                start_line=args.start_line,
                end_line=args.end_line,
                claim=args.claim,
            )
        except (OSError, UnicodeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(citation, indent=2, ensure_ascii=False))
        return 0

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    errors = validate_audit_record(record)
    if isinstance(record, dict):
        for citation in (record.get("evidence") or []) + (
            record.get("counterevidence") or []
        ):
            errors.extend(validate_citation(args.task_dir, citation))
    if errors:
        for error in sorted(set(errors)):
            print(error, file=sys.stderr)
        return 1
    print("valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
