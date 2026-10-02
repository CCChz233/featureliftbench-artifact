from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_docs.py"
SPEC = importlib.util.spec_from_file_location("check_docs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def test_markdown_links_ignore_code_examples(tmp_path: Path) -> None:
    document = tmp_path / "README.md"
    document.write_text(
        "[real](target.md)\n"
        "`render('[x](not-a-link.md)')`\n"
        "```python\nrender('![alt](also-not-a-link.png)')\n```\n",
        encoding="utf-8",
    )

    assert CHECKER.markdown_links(document) == ["target.md"]
