from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/materialize_python200_contract_v2.py"
SPEC = importlib.util.spec_from_file_location("materialize_python200_contract_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MATERIALIZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATERIALIZER)


def test_upsert_api_nests_member_under_owner() -> None:
    entries = [{"path": "featurelifted.URL", "kind": "class"}]

    MATERIALIZER.upsert_api(
        entries,
        {
            "path": "featurelifted.URL.join",
            "kind": "method",
            "signature": "(self, other)",
        },
    )

    assert entries == [
        {
            "path": "featurelifted.URL",
            "kind": "class",
            "members": [
                {
                    "path": "featurelifted.URL.join",
                    "kind": "method",
                    "signature": "(self, other)",
                }
            ],
        }
    ]


def test_remove_api_is_recursive_and_preserves_siblings() -> None:
    entries = [
        {
            "path": "featurelifted.URL",
            "kind": "class",
            "members": [
                {"path": "featurelifted.URL.join", "kind": "method"},
                {"path": "featurelifted.URL.host", "kind": "property"},
            ],
        },
        {"path": "featurelifted.parse", "kind": "function"},
    ]

    result = MATERIALIZER.remove_api(entries, {"featurelifted.URL.join"})

    assert MATERIALIZER.entry_map(result).keys() == {
        "featurelifted.URL",
        "featurelifted.URL.host",
        "featurelifted.parse",
    }


def test_reference_repair_fails_closed_on_source_drift(tmp_path: Path) -> None:
    module = tmp_path / "featurelifted.py"
    module.write_text("value = 'old'\n", encoding="utf-8")
    repair = {
        "reference_replacements": [
            {"path": "featurelifted.py", "old": "missing", "new": "new", "count": 1}
        ]
    }

    with pytest.raises(ValueError, match="expected 1 matches, found 0"):
        MATERIALIZER.apply_reference_repair(tmp_path, repair)


def test_reference_repair_replaces_exact_expected_count(tmp_path: Path) -> None:
    module = tmp_path / "featurelifted.py"
    module.write_text("value = 'old'\n", encoding="utf-8")
    repair = {
        "reference_replacements": [
            {"path": "featurelifted.py", "old": "old", "new": "new", "count": 1}
        ]
    }

    MATERIALIZER.apply_reference_repair(tmp_path, repair)

    assert module.read_text(encoding="utf-8") == "value = 'new'\n"


def test_tree_digest_ignores_runtime_cache_files(tmp_path: Path) -> None:
    module = tmp_path / "featurelifted.py"
    module.write_text("value = 1\n", encoding="utf-8")
    expected = MATERIALIZER.tree_digest(tmp_path)
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "featurelifted.cpython-312.pyc").write_bytes(b"runtime cache")
    (tmp_path / ".DS_Store").write_bytes(b"finder metadata")

    assert MATERIALIZER.tree_digest(tmp_path) == expected
