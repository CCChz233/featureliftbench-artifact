"""Unit tests for CGVL matrix expansion and workspace gate."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from featureliftbench.ablation import AblationOptions
from featureliftbench.cgvl import build_cgvl_matrix
from featureliftbench.cgvl import install_cgvl_workspace
from featureliftbench.cgvl import required_cells
from featureliftbench.metadata import load_metadata
from featureliftbench import openhands_runner


def _repo_task(*parts: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    return root.joinpath(*parts)


class CgvlMatrixTests(unittest.TestCase):
    def test_scrapy_expands_item_union_on_itemloader(self) -> None:
        task_dir = _repo_task(
            "benchmark", "tasks", "scrapy__item_loader_core__hard3_001"
        )
        if not task_dir.is_dir():
            self.skipTest(f"missing {task_dir}")
        public_spec = load_metadata(task_dir).data["public_spec"]
        matrix = build_cgvl_matrix(public_spec)
        blob = json.dumps(matrix)
        self.assertNotIn("source_entrypoints", blob)
        roles = {cell["role"] for cell in matrix["cells"]}
        self.assertIn("entry", roles)
        self.assertIn("variant", roles)
        variants = [
            cell["input_variant"]
            for cell in matrix["cells"]
            if cell["role"] == "variant"
        ]
        self.assertTrue(
            any("type[Item]" in item or "Item" in item for item in variants),
            variants,
        )
        item_arms = {
            variant
            for cell in matrix["cells"]
            if cell["role"] == "variant" and str(cell.get("input_variant") or "").startswith("item=")
            for variant in cell.get("required_variants") or []
        }
        self.assertEqual(
            item_arms,
            {"item=type[Item]", "item=Item", "item=None"},
        )
        parent_arms = {
            variant
            for cell in matrix["cells"]
            if cell["role"] == "variant"
            and str(cell.get("input_variant") or "").startswith("parent=")
            for variant in cell.get("required_variants") or []
        }
        self.assertEqual(parent_arms, {"parent=ItemLoader", "parent=None"})

    def test_decouple_builds_pairwise_quote_and_comment_cell(self) -> None:
        task_dir = _repo_task(
            "benchmark", "tasks", "python_decouple__config_repository_core__001"
        )
        if not task_dir.is_dir():
            self.skipTest(f"missing {task_dir}")
        public_spec = load_metadata(task_dir).data["public_spec"]
        matrix = build_cgvl_matrix(public_spec)
        pairwise = [cell for cell in matrix["cells"] if cell["role"] == "pairwise"]
        self.assertEqual(len(pairwise), 1, msg=pairwise)
        self.assertEqual(pairwise[0]["input_variant"], "quote AND comment")
        self.assertIn("RepositoryEnv", pairwise[0]["public_entry"])
        negative = [cell for cell in matrix["cells"] if cell["role"] == "negative"]
        self.assertTrue(negative)
        self.assertIn("Config", negative[0]["public_entry"])

    def test_pygments_does_not_treat_quoted_strings_as_env_comment_pair(self) -> None:
        task_dir = _repo_task(
            "benchmark", "python200_hard_tasks", "pygments__lexer_core__001"
        )
        if not task_dir.is_dir():
            self.skipTest(f"missing {task_dir}")
        public_spec = load_metadata(task_dir).data["public_spec"]
        matrix = build_cgvl_matrix(public_spec)
        pairwise = [cell for cell in matrix["cells"] if cell["role"] == "pairwise"]
        self.assertFalse(pairwise)
        oracle = [cell for cell in matrix["cells"] if cell["role"] == "oracle"]
        self.assertTrue(oracle)
        entry_paths = {
            str(cell.get("public_entry") or "")
            for cell in matrix["cells"]
            if cell["role"] == "entry"
        }
        self.assertEqual(
            entry_paths,
            {
                "featurelifted.lex",
                "featurelifted.get_lexer_by_name",
                "featurelifted.PythonLexer",
            },
        )
        behavior_ids = {
            str(cell.get("behavior_id") or "")
            for cell in matrix["cells"]
            if str(cell.get("behavior_id") or "").startswith("B")
        }
        self.assertTrue({"B001", "B002", "B003", "B004", "B005"}.issubset(behavior_ids))

    def test_required_api_members_are_flattened_recursively(self) -> None:
        public_spec = {
            "required_api": [
                {
                    "path": "featurelifted.testing",
                    "kind": "module",
                    "members": [
                        {
                            "path": "featurelifted.testing.Runner",
                            "kind": "class",
                            "members": [
                                {
                                    "path": "featurelifted.testing.Runner.invoke",
                                    "kind": "method",
                                    "signature": "(self, app)",
                                }
                            ],
                        }
                    ],
                }
            ],
            "behaviors": [],
        }
        matrix = build_cgvl_matrix(public_spec)
        paths = {row["path"] for row in matrix["required_api"]}
        self.assertIn("featurelifted.testing.Runner.invoke", paths)

    def test_synthetic_state_and_union_and_undetermined(self) -> None:
        public_spec = {
            "title": "Demo",
            "required_api": [
                {
                    "path": "featurelifted.AdapterRegistry",
                    "kind": "class",
                    "members": [
                        {
                            "path": "featurelifted.AdapterRegistry.unregister",
                            "kind": "method",
                            "signature": "(self, required, provided, name: str, value=None) -> bool",
                        }
                    ],
                },
                {
                    "path": "featurelifted.find_dist_info",
                    "kind": "function",
                    "signature": "(names: 'list[str]') -> 'str | None'",
                },
            ],
            "behaviors": [
                {
                    "id": "B001",
                    "text": "unregister removes only the matching registration and value.",
                }
            ],
            "source_entrypoints": ["should.not.leak"],
        }
        matrix = build_cgvl_matrix(public_spec)
        blob = json.dumps(matrix)
        self.assertNotIn("should.not.leak", blob)
        roles = {cell["role"] for cell in matrix["cells"]}
        self.assertIn("state_guard", roles)
        self.assertTrue(
            any(cell.get("undetermined") for cell in matrix["cells"]),
            msg="str | None without declared exception should be undetermined",
        )


class CgvlWorkspaceTests(unittest.TestCase):
    def test_install_and_checker_red_then_public_entry_green(self) -> None:
        public_spec = {
            "title": "Demo",
            "required_api": [
                {
                    "path": "featurelifted.Foo",
                    "kind": "function",
                    "signature": "(x: 'int') -> 'int'",
                }
            ],
            "behaviors": [{"id": "B001", "text": "Foo returns x."}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_cgvl_workspace(root, public_spec=public_spec)
            self.assertTrue((root / "cgvl_matrix.json").is_file())
            self.assertTrue((root / "run_cgvl_check.py").is_file())
            cells = json.loads((root / "cgvl_matrix.json").read_text())["cells"]
            entry = next(cell for cell in cells if cell["role"] == "entry")
            stub = root / "cgvl_cells" / f"{entry['id']}.py"
            self.assertTrue(stub.is_file())
            red = subprocess.run(
                [sys.executable, str(root / "run_cgvl_check.py"), "--workspace", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(red.returncode, 0)

            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text(
                "def Foo(x):\n    return x\n",
                encoding="utf-8",
            )
            # Fill every compact behavior cell with executable assertions and a
            # checker-recomputed counterexample witness.
            for cell in required_cells(
                json.loads((root / "cgvl_matrix.json").read_text())
            ):
                path = root / "cgvl_cells" / f"{cell['id']}.py"
                if cell.get("undetermined"):
                    path.write_text(
                        "FILLED = False\nUNDETERMINED = True\n"
                        "PUBLIC_ENTRY = %r\n"
                        "def run_featurelifted():\n    return {'result': None, 'exception_type': None}\n"
                        % (cell.get("public_entry") or "featurelifted.Foo"),
                        encoding="utf-8",
                    )
                    continue
                mutant = (cell.get("required_mutants") or ["helper_only_probe"])[0]
                minimum = int(cell.get("min_assertions") or 1)
                assertion_rows = ", ".join(
                    "{'name': 'identity_%d', 'actual': value, 'expected': 1, 'passed': value == 1}"
                    % index
                    for index in range(minimum)
                )
                path.write_text(
                    "\n".join(
                        [
                            "FILLED = True",
                            "UNDETERMINED = False",
                            "def run_featurelifted():",
                            "    from featurelifted import Foo",
                            "    value = Foo(1)",
                            "    assert value == 1",
                            "    return {",
                            "        'result': value,",
                            "        'exception_type': None,",
                            "        'assertions': [%s]," % assertion_rows,
                            "        'counterexamples': [{",
                            "            'mutant_id': %r," % mutant,
                            "            'observed': value,",
                            "            'mutant_expected': 2,",
                            "            'witness': 'Foo(1) distinguishes identity from a wrong result',",
                            "        }],",
                            "        'covered_variants': %r," % (cell.get("required_variants") or []),
                            "    }",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )
            green = subprocess.run(
                [sys.executable, str(root / "run_cgvl_check.py"), "--workspace", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            if green.returncode != 0:
                self.fail(green.stdout + green.stderr)
            payload = json.loads(green.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["finish_allowed"])
            agent_output = root / "agent_output"
            agent_output.mkdir()
            gate_code = openhands_runner._maybe_enforce_cgvl_finish_gate(
                openhands_runner.OpenHandsRunnerConfig(
                    workspace_dir=root,
                    task_file=root / "TASK.md",
                    submission_dir=root / "submission",
                    agent_output_dir=agent_output,
                ),
                {"FEATURELIFTBENCH_CGVL": "1"},
            )
            gate_record = json.loads(
                (agent_output / "cgvl_finish_gate.json").read_text()
            )
            self.assertEqual(gate_code, 0)
            self.assertTrue(gate_record["ok"])

    def test_helper_only_probe_does_not_close_public_entry(self) -> None:
        public_spec = {
            "title": "Demo",
            "required_api": [
                {
                    "path": "featurelifted.Foo",
                    "kind": "function",
                    "signature": "(x: 'int') -> 'int'",
                }
            ],
            "behaviors": [{"id": "B001", "text": "Foo returns x."}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_cgvl_workspace(root, public_spec=public_spec)
            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text(
                "def Foo(x):\n    return x\n\ndef _helper():\n    return 1\n",
                encoding="utf-8",
            )
            cells = json.loads((root / "cgvl_matrix.json").read_text())["cells"]
            entry = next(cell for cell in cells if cell["role"] == "entry")
            (root / "cgvl_cells" / f"{entry['id']}.py").write_text(
                "\n".join(
                    [
                        "CELL_ID = %r" % entry["id"],
                        "PUBLIC_ENTRY = 'featurelifted.Foo'",
                        "FILLED = True",
                        "UNDETERMINED = False",
                        "KILLS_MUTANTS = ['helper_only_probe']",
                        "def run_featurelifted():",
                        "    from featurelifted import _helper",
                        "    return {'result': _helper(), 'exception_type': None}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            red = subprocess.run(
                [sys.executable, str(root / "run_cgvl_check.py"), "--workspace", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(red.returncode, 0)
            payload = json.loads(red.stdout)
            entry_row = next(
                row for row in payload["cell_rows"] if row["id"] == entry["id"]
            )
            self.assertFalse(entry_row["public_entry_called"])
            self.assertIn("public entry", entry_row["error"])

    def test_same_named_unrelated_call_does_not_close_public_entry(self) -> None:
        public_spec = {
            "title": "Demo",
            "required_api": [
                {
                    "path": "featurelifted.Foo",
                    "kind": "function",
                    "signature": "(x: 'int') -> 'int'",
                }
            ],
            "behaviors": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_cgvl_workspace(root, public_spec=public_spec)
            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text(
                "def Foo(x):\n    return x\n",
                encoding="utf-8",
            )
            matrix = json.loads((root / "cgvl_matrix.json").read_text())
            entry = next(cell for cell in matrix["cells"] if cell["role"] == "entry")
            path = root / "cgvl_cells" / f"{entry['id']}.py"
            path.write_text(
                "\n".join(
                    [
                        "FILLED = True",
                        "UNDETERMINED = False",
                        "class Other:",
                        "    def Foo(self): return 1",
                        "def run_featurelifted():",
                        "    value = Other().Foo()",
                        "    assert value == 1",
                        "    return {'assertions': [{'name': 'x', 'actual': value, 'expected': 1, 'passed': True}], 'counterexamples': []}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            red = subprocess.run(
                [sys.executable, str(root / "run_cgvl_check.py"), "--workspace", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(red.stdout)
            row = next(item for item in payload["cell_rows"] if item["id"] == entry["id"])
            self.assertFalse(row["public_entry_called"])

    def test_declared_mutant_without_counterexample_remains_red(self) -> None:
        public_spec = {
            "title": "Demo",
            "required_api": [
                {
                    "path": "featurelifted.Foo",
                    "kind": "function",
                    "signature": "(x: 'int') -> 'int'",
                }
            ],
            "behaviors": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_cgvl_workspace(root, public_spec=public_spec)
            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text(
                "def Foo(x):\n    return x\n",
                encoding="utf-8",
            )
            matrix = json.loads((root / "cgvl_matrix.json").read_text())
            entry = next(cell for cell in matrix["cells"] if cell["role"] == "entry")
            mutant = entry["required_mutants"][0]
            path = root / "cgvl_cells" / f"{entry['id']}.py"
            path.write_text(
                "\n".join(
                    [
                        "FILLED = True",
                        "UNDETERMINED = False",
                        "KILLS_MUTANTS = [%r]" % mutant,
                        "def run_featurelifted():",
                        "    from featurelifted import Foo",
                        "    value = Foo(1)",
                        "    assert value == 1",
                        "    return {'assertions': [{'name': 'x', 'actual': value, 'expected': 1, 'passed': True}], 'counterexamples': []}",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            red = subprocess.run(
                [sys.executable, str(root / "run_cgvl_check.py"), "--workspace", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(red.stdout)
            row = next(item for item in payload["cell_rows"] if item["id"] == entry["id"])
            self.assertIn("executable counterexample", row["error"])

    def test_forbidden_submission_import_is_part_of_gate(self) -> None:
        public_spec = {
            "title": "Demo",
            "required_api": [
                {"path": "featurelifted.VALUE", "kind": "attribute"}
            ],
            "behaviors": [],
            "forbidden": {"imports": ["upstream_pkg"]},
            "isolation_behavior": {"id": "B002", "text": "No upstream import."},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_cgvl_workspace(root, public_spec=public_spec)
            submission = root / "submission" / "featurelifted"
            submission.mkdir(parents=True)
            (submission / "__init__.py").write_text(
                "import upstream_pkg\nVALUE = 1\n",
                encoding="utf-8",
            )
            red = subprocess.run(
                [sys.executable, str(root / "run_cgvl_check.py"), "--workspace", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(red.stdout)
            self.assertFalse(payload["isolation_rows"][0]["ok"])
            self.assertIn("upstream_pkg", payload["isolation_rows"][0]["error"])

    def test_runtime_finish_gate_rejects_red_checker(self) -> None:
        public_spec = {
            "title": "Demo",
            "required_api": [
                {"path": "featurelifted.Foo", "kind": "function", "signature": "(x)"}
            ],
            "behaviors": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            agent = root / "agent"
            workspace.mkdir()
            agent.mkdir()
            install_cgvl_workspace(workspace, public_spec=public_spec)
            config = openhands_runner.OpenHandsRunnerConfig(
                workspace_dir=workspace,
                task_file=workspace / "TASK.md",
                submission_dir=workspace / "submission",
                agent_output_dir=agent,
            )
            code = openhands_runner._maybe_enforce_cgvl_finish_gate(
                config,
                {"FEATURELIFTBENCH_CGVL": "1"},
            )
            record = json.loads((agent / "cgvl_finish_gate.json").read_text())
            self.assertEqual(code, openhands_runner.CGVL_FINISH_GATE_RETURN_CODE)
            self.assertFalse(record["ok"])

    def test_clause_with_braces_does_not_break_stub_install(self) -> None:
        public_spec = {
            "title": "Demo",
            "required_api": [
                {
                    "path": "featurelifted.Foo",
                    "kind": "function",
                    "signature": "(x: 'int') -> 'int'",
                }
            ],
            "behaviors": [
                {
                    "id": "B001",
                    "text": "unregister {0} must not change other registrations.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_cgvl_workspace(root, public_spec=public_spec)
            stub = next((root / "cgvl_cells").glob("*state*.py"))
            self.assertIn("{0}", stub.read_text(encoding="utf-8"))


class CgvlAblationTests(unittest.TestCase):
    def test_arm_name_and_exclusion(self) -> None:
        self.assertEqual(AblationOptions(cgvl=True).ablation_arm, "cgvl")
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(cgvl=True, spec_adversarial_self_test=True)


if __name__ == "__main__":
    unittest.main()
