"""Execute a subprocess command under a POSIX virtual-memory limit."""

from __future__ import annotations

import os
import resource
import sys


def _apply_memory_limit(memory_mb: int) -> None:
    if memory_mb <= 0:
        return
    limit = memory_mb * 1024 * 1024
    for resource_type in (resource.RLIMIT_AS, resource.RLIMIT_DATA):
        try:
            resource.setrlimit(resource_type, (limit, limit))
            return
        except (ValueError, OSError):
            continue
    print(
        f"warning: could not set memory limit to {memory_mb}MB; continuing without cap",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print("usage: python -m featureliftbench.run_limited <memory_mb> <command...>", file=sys.stderr)
        return 2
    memory_mb = int(args[0])
    command = args[1:]
    _apply_memory_limit(memory_mb)
    os.execvp(command[0], command)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
