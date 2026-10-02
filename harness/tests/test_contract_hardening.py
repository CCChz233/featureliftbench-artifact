from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from featureliftbench.task_render import render_public_task
from featureliftbench.task_spec_migrate import _render_required_api_surface_test


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "archive" / "harden_experiment_contracts.py"
SPEC = importlib.util.spec_from_file_location("harden_experiment_contracts", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
HARDENER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARDENER)


class ContractHardeningTests(unittest.TestCase):
    def test_isinstance_narrows_union_return_before_member_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            hidden = task_dir / "hidden_tests"
            hidden.mkdir()
            (hidden / "test_hidden_behavior.py").write_text(
                "\n".join(
                    [
                        "from featurelifted import Date, Duration, parse",
                        "",
                        "def test_duration():",
                        "    result = parse('P2W')",
                        "    assert isinstance(result, Duration)",
                        "    assert result.in_days() == 14",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            required_api = [
                {"path": "featurelifted.Date", "kind": "class"},
                {"path": "featurelifted.Duration", "kind": "class"},
                {
                    "path": "featurelifted.parse",
                    "kind": "function",
                    "signature": "(text: str) -> Date | Duration",
                },
            ]

            usage = HARDENER._hidden_member_usage(task_dir, required_api)

        self.assertIn("featurelifted.Duration.in_days", usage)
        self.assertNotIn("featurelifted.Date.in_days", usage)

    def test_generic_behavior_uses_matching_included_behavior_position(self) -> None:
        metadata = {
            "feature": {"included_behaviors": ["first behavior", "second behavior"]},
            "public_spec": {
                "required_api": [
                    {
                        "path": "featurelifted.extract",
                        "kind": "function",
                        "signature": "(value)",
                    }
                ],
                "behaviors": [
                    {"id": "B001", "text": "Already concrete."},
                    {
                        "id": "B002",
                        "text": (
                            "preserves the corresponding upstream-observable result "
                            "within the documented scope"
                        ),
                    },
                ],
            },
            "evaluation_spec": {
                "public_clauses": [
                    {"behavior_id": "B001", "clause_kind": "included_behavior"},
                    {"behavior_id": "B002", "clause_kind": "included_behavior"},
                ],
                "hidden_test_mappings": [],
                "public_test_mappings": [],
            },
        }

        hardened = HARDENER._harden_behavior_texts(metadata)

        self.assertIn("second behavior", hardened["B002"])

    def test_nested_class_members_are_visible_and_runtime_bound_surface_is_safe(
        self,
    ) -> None:
        required_api = [
            {
                "path": "featurelifted.models",
                "kind": "module",
                "members": [
                    {
                        "path": "featurelifted.models.Proxy",
                        "kind": "class",
                        "signature": "()",
                        "members": [
                            {
                                "path": "featurelifted.models.Proxy.generate",
                                "kind": "method",
                                "signature": "() -> str",
                                "runtime_bound": True,
                            },
                            {
                                "path": "featurelifted.models.Proxy.static_generate",
                                "kind": "method",
                                "signature": "(self) -> str",
                            },
                            {
                                "path": "featurelifted.models.Proxy.value",
                                "kind": "attribute",
                            },
                        ],
                    }
                ],
            }
        ]
        metadata = {
            "task_id": "example",
            "source": {"name": "upstream"},
            "public_spec": {
                "title": "Example",
                "summary": "Extract an example.",
                "source_entrypoints": ["repo/example.py"],
                "required_api": required_api,
                "behaviors": [],
                "exclusions": [],
                "forbidden": {"imports": [], "paths": []},
            },
        }

        rendered = render_public_task(metadata)
        surface = _render_required_api_surface_test(required_api, task_id="example")

        self.assertIn("`models.Proxy.generate() -> str`", rendered)
        self.assertIn("`models.Proxy.value` attribute must exist on instances", rendered)
        self.assertIn("runtime-bound method", surface)
        self.assertIn(
            "hasattr(getattr(models, 'Proxy'), 'static_generate')",
            surface,
        )
        self.assertNotIn("hasattr(models, 'static_generate')", surface)


if __name__ == "__main__":
    unittest.main()
