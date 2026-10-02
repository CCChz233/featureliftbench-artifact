from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/generate_contract_api_patches.py"
SPEC = importlib.util.spec_from_file_location("generate_contract_api_patches", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


def test_ast_usage_detects_called_featurelifted_symbol(tmp_path: Path) -> None:
    public = tmp_path / "public_tests"
    public.mkdir()
    (public / "test_api.py").write_text(
        "from featurelifted import URL\n\ndef test_url():\n    URL('https://example.com')\n",
        encoding="utf-8",
    )

    usage = GENERATOR.ast_usage(tmp_path)

    assert usage["featurelifted.URL"]["called"] is True
    assert usage["featurelifted.URL"]["evidence"] == ["public_tests/test_api.py:4"]


def test_expression_path_handles_nested_import() -> None:
    tree = ast.parse("from featurelifted import routing\nrouting.Map([])\n")
    imported = GENERATOR.imported_paths(tree)
    call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call))

    assert GENERATOR.expression_path(call.func, imported) == "featurelifted.routing.Map"
