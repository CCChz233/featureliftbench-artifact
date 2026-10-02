"""Launch OpenHands after registering FeatureLiftBench condensers."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path


def resolve_openhands_cli_main() -> Callable[..., object]:
    """Locate the pinned OpenHands CLI entry (1.16 uses entrypoint.main)."""

    try:
        from openhands_cli.entrypoint import main as openhands_main
    except ImportError:
        from openhands_cli.main import main as openhands_main
    return openhands_main


def _write_launch_heartbeat() -> None:
    output = os.environ.get("FEATURELIFTBENCH_AGENT_OUTPUT_DIR", "").strip()
    if not output and Path("/flb/agent").is_dir():
        output = "/flb/agent"
    if not output:
        return
    payload = {
        "event": "launch",
        "mode": os.environ.get("FEATURELIFTBENCH_OPENHANDS_CONDENSER_MODE", ""),
        "agent_output_dir": os.environ.get("FEATURELIFTBENCH_AGENT_OUTPUT_DIR", ""),
    }
    try:
        Path(output).mkdir(parents=True, exist_ok=True)
        Path(output, "condenser_launch.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return


def main(argv: list[str] | None = None) -> None:
    from featureliftbench.openhands_condenser.patch import apply_openhands_condenser_patch

    apply_openhands_condenser_patch()
    _write_launch_heartbeat()
    args = list(sys.argv[1:] if argv is None else argv)
    sys.argv = ["openhands", *args]
    raise SystemExit(resolve_openhands_cli_main()())


if __name__ == "__main__":
    main()
