from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.ablation import AblationOptions
from featureliftbench.agent_adapters import AgentCommandResult
from featureliftbench.agent_adapters import AgentRunConfig
from featureliftbench.agent_runner import run_agent_on_task
from featureliftbench.contract_closure_gate import check_workspace
from featureliftbench.contract_closure_gate import check_workspace_isolated
from featureliftbench.contract_closure_gate import decide_repair
from featureliftbench.contract_closure_gate import install_contract_closure_workspace
from featureliftbench.contract_closure_gate import openhands_appendix
from featureliftbench.contract_closure_gate import prepare_repair_workspace
from featureliftbench.contract_closure_gate import task_appendix
from featureliftbench.contract_closure_gate import write_contract_closure_audit
from featureliftbench.contract_closure_gate.common import LITE_V1_SILENT_FINISH_ENV
from featureliftbench.contract_closure_gate.checker import compare_signature
from featureliftbench.contract_closure_gate.checker import parse_public_signature


def _metadata() -> dict:
    return {
        "task_id": "contract_gate_demo",
        "public_spec": {
            "title": "Contract gate demo",
            "summary": "Exercise every supported public API category.",
            "required_api": [
                {"path": "featurelifted.submodule", "kind": "module"},
                {
                    "path": "featurelifted.Thing",
                    "kind": "class",
                    "members": [
                        {
                            "path": "featurelifted.Thing.method",
                            "kind": "method",
                            "signature": "(self, value=2)",
                        },
                        {"path": "featurelifted.Thing.class_attr", "kind": "attribute"},
                    ],
                },
                {"path": "featurelifted.Problem", "kind": "exception"},
                {
                    "path": "featurelifted.wildcard",
                    "kind": "function",
                    "signature": "(value, ...)",
                },
                {
                    "path": "featurelifted.factory_default",
                    "kind": "function",
                    "signature": "(value: object = <factory>)",
                },
                {"path": "featurelifted.CONSTANT", "kind": "constant"},
                {"path": "featurelifted.OBJ", "kind": "object"},
                {"path": "featurelifted.proxy.dynamic", "kind": "attribute"},
            ],
            "optional_api": [],
            "behaviors": [
                {"id": "B001", "text": "wildcard doubles its first numeric argument."},
                {
                    "id": "B002",
                    "text": "the published state remains equal to constant three.",
                },
            ],
            "exclusions": [],
            "forbidden": {"imports": ["original"], "paths": ["repo/"]},
        },
    }


def _materialize_workspace(root: Path) -> Path:
    workspace = root / "workspace"
    workspace.mkdir()
    install_contract_closure_workspace(workspace, metadata=_metadata())
    repo = workspace / "repo"
    repo.mkdir()
    (repo / "original.py").write_text(
        "def double(value):\n    return value * 2\n", encoding="utf-8"
    )
    package = workspace / "submission" / "featurelifted"
    package.mkdir(parents=True)
    (package / "submodule.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from . import submodule\n"
        "class Thing:\n"
        "    class_attr = 1\n"
        "    def method(self, value=2):\n"
        "        return value\n"
        "class Problem(Exception):\n"
        "    pass\n"
        "def wildcard(value, extra=None):\n"
        "    return value * 2\n"
        "_DEFAULT = object()\n"
        "def factory_default(value=_DEFAULT):\n"
        "    return value\n"
        "CONSTANT = 3\n"
        "OBJ = object()\n"
        "class Proxy:\n"
        "    def __getattr__(self, name):\n"
        "        return 1\n"
        "proxy = Proxy()\n",
        encoding="utf-8",
    )
    cases = workspace / "contract_cases"
    (cases / "case_double.py").write_text(
        'CASE_ID = "double"\n'
        'BEHAVIOR_IDS = ["B001"]\n'
        'REQUIRED_API = ["featurelifted.wildcard"]\n'
        'MODE = "differential"\n'
        'EVIDENCE = ["public_spec:B001", "repo/original.py:1"]\n'
        "def run_upstream():\n"
        "    from original import double\n"
        "    return {'result': double(4), 'exception': None, 'state_after': None}\n"
        "def run_featurelifted():\n"
        "    from featurelifted import wildcard\n"
        "    return {'result': wildcard(4), 'exception': None, 'state_after': None}\n",
        encoding="utf-8",
    )
    (cases / "case_constant.py").write_text(
        'CASE_ID = "constant"\n'
        'BEHAVIOR_IDS = ["B002"]\n'
        'REQUIRED_API = ["featurelifted.CONSTANT"]\n'
        'MODE = "direct"\n'
        'EVIDENCE = ["public_spec:B002"]\n'
        "def check_featurelifted():\n"
        "    import featurelifted\n"
        "    assert featurelifted.CONSTANT == 3\n",
        encoding="utf-8",
    )
    return workspace


class ContractClosureGateTests(unittest.TestCase):
    def test_lite_v1_frozen_prompt_matches_pilot_protocol(self) -> None:
        with mock.patch.dict(os.environ, {LITE_V1_SILENT_FINISH_ENV: ""}, clear=False):
            prompt = openhands_appendix(lite=True, frozen_v1=True)

        self.assertIn("Implement the submission, then run", prompt)
        self.assertIn("--structure-only --summary", prompt)
        self.assertIn("Do not create contract_cases", prompt)
        self.assertIn("deterministic public API closure only", prompt)
        self.assertNotIn("6 agent steps", prompt)
        self.assertNotIn("70%", prompt)

    def test_lite_v1_silent_finish_prompt_drops_stop_policy(self) -> None:
        with mock.patch.dict(os.environ, {LITE_V1_SILENT_FINISH_ENV: "1"}, clear=False):
            prompt = openhands_appendix(lite=True, frozen_v1=True)
            task = task_appendix(lite=True, frozen_v1=True)

        self.assertIn("Implement the submission, then run", prompt)
        self.assertIn("--structure-only --summary", prompt)
        self.assertIn("Do not create contract_cases", prompt)
        self.assertNotIn("deterministic public API closure only", prompt)
        self.assertNotIn("completion signal", prompt)
        self.assertNotIn("not a reason to finish", prompt)
        self.assertNotIn("keep using remaining steps", prompt)
        self.assertNotIn("before finishing", task)
        self.assertNotIn("structural gate", task)
        self.assertNotIn("Do not treat a passing structure check", task)
        self.assertIn("after submission", task)

    def test_lite_rescue_prompt_keeps_v1_focus_without_frozen_identity(self) -> None:
        prompt = openhands_appendix(lite=True, rescue=True)

        self.assertIn("Implement the submission, then run", prompt)
        self.assertIn("--structure-only --summary", prompt)
        self.assertNotIn("6 agent steps", prompt)
        self.assertNotIn("70%", prompt)

    def test_lite_v2_prompt_requires_early_implementation_checkpoints(self) -> None:
        prompt = openhands_appendix(lite=True)

        self.assertIn("writing, not by exhaustively reading", prompt)
        self.assertIn("6 agent steps", prompt)
        self.assertIn("step 12", prompt)
        self.assertIn("70%", prompt)

    def test_v3_prompt_limits_behavior_work_to_two_micro_cases(self) -> None:
        prompt = openhands_appendix(lite=True, v3=True)

        self.assertIn("exactly two", prompt)
        self.assertIn("never more than three", prompt)
        self.assertIn("--micro", prompt)
        self.assertIn("Do not chase full", prompt)

    def test_lite_rescue_plus_prompt_has_smoke_and_finish_budget(self) -> None:
        prompt = openhands_appendix(lite=True, rescue_plus=True)

        self.assertIn("PUBLIC_WITNESS.json", prompt)
        self.assertIn("exactly one direct case", prompt)
        self.assertIn("--lite-plus", prompt)
        self.assertIn("step 32", prompt)
        self.assertIn("selected public clause is the primary oracle", prompt)
        self.assertIn("never causes a paid repair", prompt)

    def test_complete_workspace_passes_with_dynamic_attribute_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))

            result = check_workspace(workspace)

            self.assertTrue(result["hard_gate_ok"])
            self.assertTrue(result["behavior_gate_ok"])
            self.assertTrue(result["closure_ok"])
            self.assertEqual(result["required_api_count"], 10)
            by_id = {item["id"]: item for item in result["checks"]}
            self.assertEqual(
                by_id["api.featurelifted.proxy.dynamic"]["status"], "unknown"
            )
            self.assertEqual(
                by_id["signature.featurelifted.Thing.method"]["status"], "pass"
            )
            self.assertEqual(by_id["behavior.case.double"]["status"], "pass")
            self.assertEqual(by_id["behavior.case.constant"]["status"], "pass")

    def test_lite_rescue_plus_missing_witness_is_telemetry_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            install_contract_closure_workspace(
                workspace,
                metadata=_metadata(),
                lite=True,
                rescue_plus=True,
            )
            for path in (workspace / "contract_cases").glob("*.py"):
                path.unlink()

            result = check_workspace(workspace, check_mode="lite_plus")
            by_id = {item["id"]: item for item in result["checks"]}
            decision = decide_repair(
                workspace,
                result,
                lite=True,
                rescue_plus=True,
            )

            self.assertFalse(result["behavior_gate_ok"])
            self.assertFalse(result["repair_needed"])
            self.assertEqual(by_id["behavior.witness.required"]["status"], "fail")
            self.assertFalse(decision["eligible"])
            self.assertEqual(
                decision["policy_version"],
                "contract_closure_gate_lite_rescue_plus.v2.2",
            )
            self.assertEqual(decision["repair_kind"], "none")
            self.assertIn("telemetry only", decision["reason"])

    def test_differential_rejects_non_envelope_dict_without_false_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            case = workspace / "contract_cases" / "case_double.py"
            text = case.read_text(encoding="utf-8")
            text = text.replace(
                "return {'result': double(4), 'exception': None, 'state_after': None}",
                "return {'composed': double(4)}",
            )
            text = text.replace(
                "return {'result': wildcard(4), 'exception': None, 'state_after': None}",
                "return {'composed': wildcard(4)}",
            )
            case.write_text(text, encoding="utf-8")

            result = check_workspace(workspace, check_mode="lite_plus")
            by_id = {item["id"]: item for item in result["checks"]}
            decision = decide_repair(
                workspace,
                result,
                lite=True,
                rescue_plus=True,
            )

            invalid = by_id["behavior.case.double"]
            self.assertEqual(invalid["status"], "fail")
            self.assertEqual(invalid["category"], "behavior_evidence")
            self.assertIn("protocol invalid", invalid["message"])
            self.assertFalse(result["behavior_gate_ok"])
            self.assertFalse(result["repair_needed"])
            self.assertEqual(decision["repair_kind"], "none")

    def test_differential_mismatch_is_not_selected_direct_witness_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            case = workspace / "contract_cases" / "case_double.py"
            text = case.read_text(encoding="utf-8")
            text = text.replace(
                "return {'result': wildcard(4), 'exception': None, 'state_after': None}",
                "return {'result': wildcard(4), 'exception': None, "
                "'state_after': 'wrong'}",
            )
            case.write_text(text, encoding="utf-8")

            result = check_workspace(workspace, check_mode="lite_plus")
            decision = decide_repair(
                workspace,
                result,
                lite=True,
                rescue_plus=True,
            )

            mismatch = next(
                item
                for item in result["checks"]
                if item["id"] == "behavior.case.double"
            )
            self.assertEqual(mismatch["status"], "fail")
            self.assertEqual(mismatch["category"], "behavior")
            self.assertIn("differs from stable upstream", mismatch["message"])
            self.assertEqual(decision["repair_kind"], "none")
            self.assertFalse(decision["eligible"])

    def test_selected_direct_witness_failure_is_repairable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            install_contract_closure_workspace(
                workspace,
                metadata=_metadata(),
                lite=True,
                rescue_plus=True,
            )
            package = workspace / "submission" / "featurelifted" / "__init__.py"
            package.write_text(
                package.read_text(encoding="utf-8").replace("CONSTANT = 3", "CONSTANT = 4"),
                encoding="utf-8",
            )

            result = check_workspace(workspace, check_mode="lite_plus")
            decision = decide_repair(
                workspace,
                result,
                lite=True,
                rescue_plus=True,
            )
            witness = next(
                item
                for item in result["checks"]
                if item["id"] == "behavior.case.constant"
            )

            self.assertEqual(result["public_witness_behavior_id"], "B002")
            self.assertTrue(witness["evidence"]["public_witness"])
            self.assertTrue(result["repair_needed"])
            self.assertTrue(decision["eligible"])
            self.assertEqual(decision["repair_kind"], "defect_repair")
            self.assertIn("selected direct", decision["reason"])

    def test_rescue_plus_empty_submission_is_bootstrap_repairable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            install_contract_closure_workspace(
                workspace,
                metadata=_metadata(),
                lite=True,
                rescue_plus=True,
            )

            result = check_workspace(workspace, check_mode="lite_plus")
            decision = decide_repair(
                workspace,
                result,
                lite=True,
                rescue_plus=True,
            )

            self.assertTrue(decision["eligible"])
            self.assertEqual(decision["python_file_count"], 0)
            self.assertIn("submission:bootstrap", decision["repair_clusters"])
            self.assertIn("empty submission bootstrap", decision["reason"])

    def test_rescue_plus_groups_many_api_failures_by_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            package = workspace / "submission" / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            failures = []
            for module in ("markup", "text"):
                failures.append(
                    {
                        "id": f"api.featurelifted.{module}",
                        "category": "api",
                        "status": "fail",
                        "severity": "hard",
                        "target": f"featurelifted.{module}",
                        "evidence": {"kind": "module"},
                    }
                )
                for member in ("first", "second"):
                    failures.append(
                        {
                            "id": f"api.featurelifted.{module}.{member}",
                            "category": "api",
                            "status": "fail",
                            "severity": "hard",
                            "target": f"featurelifted.{module}.{member}",
                            "evidence": {"kind": "function"},
                        }
                    )
            failures.append(
                {
                    "id": "forbidden.imports",
                    "category": "dependency",
                    "status": "fail",
                    "severity": "hard",
                    "target": "submission/",
                }
            )

            decision = decide_repair(
                workspace,
                {"repair_needed": True, "checks": failures},
                lite=True,
                rescue_plus=True,
            )

            self.assertEqual(len(failures), 7)
            self.assertTrue(decision["eligible"])
            self.assertEqual(decision["repair_cluster_count"], 3)

    def test_lite_rescue_plus_external_dependency_unknown_does_not_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            package = workspace / "submission" / "featurelifted" / "__init__.py"
            package.write_text(
                "import definitely_missing_checker_dependency\n",
                encoding="utf-8",
            )
            cases = workspace / "contract_cases"
            for path in cases.glob("*.py"):
                path.unlink()
            (cases / "case_unknown.py").write_text(
                'CASE_ID = "unknown-dependency"\n'
                'BEHAVIOR_IDS = ["B001"]\n'
                'REQUIRED_API = ["featurelifted.Thing"]\n'
                'MODE = "direct"\n'
                'EVIDENCE = ["public_spec:B001"]\n'
                "def check_featurelifted():\n"
                "    import featurelifted\n"
                "    assert featurelifted is not None\n",
                encoding="utf-8",
            )

            result = check_workspace(workspace, check_mode="lite_plus")
            decision = decide_repair(
                workspace,
                result,
                lite=True,
                rescue_plus=True,
            )

            self.assertFalse(result["closure_ok"])
            self.assertFalse(result["repair_needed"])
            self.assertGreater(result["unknown_count"], 0)
            self.assertFalse(decision["eligible"])

    def test_lite_rescue_plus_caps_cases_and_records_shared_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            source = workspace / "contract_cases" / "case_constant.py"
            third = source.read_text(encoding="utf-8").replace(
                'CASE_ID = "constant"', 'CASE_ID = "third"'
            )
            (workspace / "contract_cases" / "case_third.py").write_text(
                third,
                encoding="utf-8",
            )

            result = check_workspace(workspace, check_mode="lite_plus")
            by_id = {item["id"]: item for item in result["checks"]}

            self.assertEqual(result["behavior_execution_budget_seconds"], 60)
            self.assertEqual(by_id["behavior.case.limit"]["status"], "fail")
            self.assertNotIn("behavior.case.third", by_id)

    def test_missing_api_and_wrong_literal_default_are_hard_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            package = workspace / "submission" / "featurelifted" / "__init__.py"
            text = package.read_text(encoding="utf-8")
            text = text.replace(
                "def wildcard(value, extra=None):", "def wildcard(value=9, extra=None):"
            )
            text = text.replace(
                "class Problem(Exception):", "class NotProblem(Exception):"
            )
            package.write_text(text, encoding="utf-8")

            result = check_workspace(workspace)
            by_id = {item["id"]: item for item in result["checks"]}

            self.assertFalse(result["hard_gate_ok"])
            self.assertEqual(by_id["api.featurelifted.Problem"]["status"], "fail")
            self.assertEqual(
                by_id["signature.featurelifted.wildcard"]["status"], "fail"
            )
            self.assertTrue(result["repair_needed"])

    def test_missing_checker_dependency_is_unknown_and_does_not_request_repair(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            package = workspace / "submission" / "featurelifted" / "__init__.py"
            package.write_text(
                "import flb_dependency_that_is_not_installed\n"
                + package.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            result = check_workspace(workspace, check_mode="structure")
            api_checks = [
                item for item in result["checks"] if item["category"] == "api"
            ]

            self.assertTrue(api_checks)
            self.assertTrue(all(item["status"] == "unknown" for item in api_checks))
            self.assertTrue(result["hard_gate_ok"])
            self.assertFalse(result["repair_needed"])
            self.assertEqual(
                result["checker_environment_unknown_count"], len(api_checks)
            )

    def test_missing_submission_internal_module_remains_a_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            package = workspace / "submission" / "featurelifted" / "__init__.py"
            package.write_text(
                "from .missing_internal_module import VALUE\n",
                encoding="utf-8",
            )

            result = check_workspace(workspace, check_mode="structure")
            api_checks = [
                item for item in result["checks"] if item["category"] == "api"
            ]

            self.assertTrue(any(item["status"] == "fail" for item in api_checks))
            self.assertFalse(result["hard_gate_ok"])
            self.assertTrue(result["repair_needed"])

    def test_forbidden_import_and_vacuous_behavior_case_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            package = workspace / "submission" / "featurelifted" / "__init__.py"
            package.write_text(
                "import original\n" + package.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            direct = workspace / "contract_cases" / "case_constant.py"
            direct.write_text(
                direct.read_text(encoding="utf-8").replace(
                    "assert featurelifted.CONSTANT == 3", "assert True"
                ),
                encoding="utf-8",
            )

            result = check_workspace(workspace)
            by_id = {item["id"]: item for item in result["checks"]}

            self.assertEqual(by_id["forbidden.imports"]["status"], "fail")
            self.assertEqual(by_id["behavior.case.case_constant"]["status"], "fail")
            self.assertFalse(result["behavior_gate_ok"])

    def test_structure_only_and_soft_coverage_do_not_trigger_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            for path in (workspace / "contract_cases").glob("*.py"):
                path.unlink()

            structure = check_workspace(workspace, check_mode="structure")
            full = check_workspace(workspace)

            self.assertTrue(structure["closure_ok"])
            self.assertEqual(structure["check_mode"], "structure")
            self.assertFalse(full["behavior_gate_ok"])
            self.assertGreater(full["soft_open_count"], 0)
            self.assertEqual(full["actionable_behavior_failure_count"], 0)
            self.assertFalse(full["repair_needed"])

    def test_v3_micro_mode_uses_executed_case_without_requiring_full_coverage(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            (workspace / "contract_cases" / "case_constant.py").unlink()

            full = check_workspace(workspace)
            micro = check_workspace(workspace, check_mode="micro")

            self.assertFalse(full["behavior_gate_ok"])
            self.assertTrue(micro["behavior_gate_ok"])
            self.assertTrue(micro["closure_ok"])
            self.assertEqual(micro["micro_behavior_pass_count"], 1)
            self.assertFalse(micro["repair_needed"])
            uncovered = next(
                item
                for item in micro["checks"]
                if item["id"] == "behavior.coverage.B002"
            )
            self.assertEqual(uncovered["status"], "fail")

    def test_v3_micro_mode_caps_executed_cases_at_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            original = workspace / "contract_cases" / "case_constant.py"
            for index in range(3):
                copy = workspace / "contract_cases" / f"case_extra_{index}.py"
                copy.write_text(
                    original.read_text(encoding="utf-8").replace(
                        'CASE_ID = "constant"', f'CASE_ID = "extra_{index}"'
                    ),
                    encoding="utf-8",
                )

            result = check_workspace(workspace, check_mode="micro")
            by_id = {item["id"]: item for item in result["checks"]}

            self.assertEqual(by_id["behavior.case.limit"]["status"], "fail")
            executed = [
                item
                for item in result["checks"]
                if item.get("category") == "behavior"
                and isinstance(item.get("evidence"), dict)
                and "runtime" in item["evidence"]
            ]
            self.assertEqual(len(executed), 3)

    def test_upstream_import_environment_failure_is_unknown_not_actionable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            case = workspace / "contract_cases" / "case_double.py"
            text = case.read_text(encoding="utf-8")
            text = text.replace(
                "return {'result': double(4), 'exception': None, 'state_after': None}",
                "return {'result': [{'result': None, 'exception': 'ImportError', "
                "'state_after': 'dependency unavailable'}], 'exception': None, "
                "'state_after': None}",
            )
            case.write_text(text, encoding="utf-8")

            result = check_workspace(workspace)
            by_id = {item["id"]: item for item in result["checks"]}

            self.assertEqual(by_id["behavior.case.double"]["status"], "unknown")
            self.assertIn("dependency environment", by_id["behavior.case.double"]["message"])
            self.assertEqual(result["actionable_behavior_failure_count"], 0)
            self.assertFalse(result["repair_needed"])

    def test_isolated_checker_uses_agent_image_and_cleans_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            isolated_result = workspace / ".contract_closure_isolated.json"

            def fake_docker(_workspace, argv, **kwargs):
                self.assertIn("--structure-only", argv)
                self.assertTrue(kwargs["mount_harness"])
                isolated_result.write_text(
                    json.dumps({"closure_ok": True, "check_mode": "structure"}),
                    encoding="utf-8",
                )
                return mock.MagicMock(returncode=0, stdout="", stderr="")

            with mock.patch(
                "featureliftbench.contract_closure_gate.isolation.run_command_in_agent_docker",
                side_effect=fake_docker,
            ):
                result = check_workspace_isolated(
                    workspace,
                    use_docker=True,
                    docker_image="agent:test",
                    check_mode="structure",
                )

            self.assertEqual(result["execution_environment"]["backend"], "agent_docker")
            self.assertEqual(result["execution_environment"]["image"], "agent:test")
            self.assertFalse(isolated_result.exists())

    def test_workspace_wrapper_supports_staged_summary_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = _materialize_workspace(Path(tmp))
            harness_root = Path(__file__).resolve().parents[1]
            completed = subprocess.run(
                [
                    sys.executable,
                    str(workspace / "flb-contract-check"),
                    "--structure-only",
                    "--summary",
                ],
                cwd=workspace,
                env={**os.environ, "PYTHONPATH": str(harness_root)},
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            shown = json.loads(completed.stdout)
            self.assertEqual(shown["check_mode"], "structure")
            self.assertTrue(shown["closure_ok"])
            self.assertIn("failed_checks", shown)

    def test_public_contract_contains_no_private_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            metadata = _metadata()
            metadata["evaluation_spec"] = {"hidden_test_mappings": ["secret"]}
            metadata["scoring_reference"] = "secret"

            install_contract_closure_workspace(workspace, metadata=metadata)
            payload = json.loads((workspace / "PUBLIC_CONTRACT.json").read_text())
            serialized = json.dumps(payload)

            self.assertNotIn("evaluation_spec", serialized)
            self.assertNotIn("hidden_test_mappings", serialized)
            self.assertNotIn("scoring_reference", serialized)
            self.assertEqual(
                set(payload),
                {
                    "schema_version",
                    "generator_version",
                    "task_id",
                    "spec_hash",
                    "public_spec",
                    "contract_hash",
                },
            )

    def test_all_python200_signatures_normalize(self) -> None:
        root = Path(__file__).resolve().parents[2] / "benchmark" / "python200_tasks"
        parsed = 0

        def walk(items):
            for item in items:
                yield item
                yield from walk(item.get("members") or [])

        for metadata_path in root.glob("*/metadata.json"):
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            for entry in walk(metadata["public_spec"]["required_api"]):
                signature = entry.get("signature")
                if signature:
                    parse_public_signature(signature)
                    parsed += 1
        self.assertGreater(parsed, 800)

    def test_signature_comparison_rejects_unpublished_extra_parameters(
        self,
    ) -> None:
        compatible = {
            "available": True,
            "text": "(value, option=None)",
            "parameters": [
                {
                    "name": "value",
                    "kind": "POSITIONAL_OR_KEYWORD",
                    "has_default": False,
                    "default_repr": None,
                },
                {
                    "name": "option",
                    "kind": "POSITIONAL_OR_KEYWORD",
                    "has_default": True,
                    "default_repr": "None",
                },
            ],
        }
        incompatible = json.loads(json.dumps(compatible))
        incompatible["parameters"][1]["has_default"] = False
        incompatible["parameters"][1]["default_repr"] = None

        self.assertEqual(compare_signature("(value)", compatible)[0], "fail")
        self.assertEqual(compare_signature("(value)", incompatible)[0], "fail")
        self.assertEqual(compare_signature("(value, ...)", compatible)[0], "pass")

    def test_signature_comparison_ignores_unpublished_method_receiver(self) -> None:
        actual = {
            "available": True,
            "text": "(cls, text: str, *, style='')",
            "parameters": [
                {
                    "name": "cls",
                    "kind": "POSITIONAL_OR_KEYWORD",
                    "has_default": False,
                    "default_repr": None,
                },
                {
                    "name": "text",
                    "kind": "POSITIONAL_OR_KEYWORD",
                    "has_default": False,
                    "default_repr": None,
                },
                {
                    "name": "style",
                    "kind": "KEYWORD_ONLY",
                    "has_default": True,
                    "default_repr": "''",
                },
            ],
        }

        self.assertEqual(
            compare_signature(
                "(text: str, *, style='')", actual, implicit_receiver=True
            )[0],
            "pass",
        )
        self.assertEqual(
            compare_signature("(text: str, *, style='')", actual)[0], "fail"
        )

    def test_lite_v2_repair_policy_rejects_empty_and_broad_submissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "submission").mkdir()
            empty = {
                "repair_needed": True,
                "checks": [
                    {
                        "id": "submission.python_files",
                        "category": "structure",
                        "status": "fail",
                        "severity": "hard",
                    }
                ],
            }
            decision = decide_repair(workspace, empty, lite=True)
            self.assertFalse(decision["eligible"])
            self.assertIn("empty submission", decision["reason"])

            package = workspace / "submission" / "featurelifted"
            package.mkdir()
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            broad = {
                "repair_needed": True,
                "checks": [
                    {
                        "id": f"api.featurelifted.missing_{index}",
                        "category": "api",
                        "status": "fail",
                        "severity": "hard",
                    }
                    for index in range(4)
                ],
            }
            decision = decide_repair(workspace, broad, lite=True)
            self.assertFalse(decision["eligible"])
            self.assertIn("exceed", decision["reason"])

    def test_lite_v2_repair_policy_accepts_small_local_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package = workspace / "submission" / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            local = {
                "repair_needed": True,
                "checks": [
                    {
                        "id": "signature.featurelifted.func",
                        "category": "signature",
                        "status": "fail",
                        "severity": "hard",
                    }
                ],
            }

            decision = decide_repair(workspace, local, lite=True)

            self.assertTrue(decision["eligible"])
            self.assertIn("local", decision["reason"])

            rescue_decision = decide_repair(
                workspace,
                local,
                lite=True,
                rescue=True,
            )
            self.assertTrue(rescue_decision["eligible"])
            self.assertEqual(
                rescue_decision["policy_version"],
                "contract_closure_gate_lite_rescue.v1",
            )

    def test_v3_repair_policy_accepts_concrete_behavior_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package = workspace / "submission" / "featurelifted"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            mismatch = {
                "repair_needed": True,
                "checks": [
                    {
                        "id": "behavior.case.edge",
                        "category": "behavior",
                        "status": "fail",
                        "severity": "soft",
                        "message": "direct assertion failed: AssertionError",
                    }
                ],
            }

            decision = decide_repair(workspace, mismatch, lite=True, v3=True)

            self.assertTrue(decision["eligible"])
            self.assertEqual(decision["policy_version"], "contract_closure_gate.v3")
            self.assertIn("behavior", decision["reason"])

    def test_repair_report_is_concise_and_includes_public_clause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            install_contract_closure_workspace(workspace, metadata=_metadata())
            result = {
                "hard_gate_ok": True,
                "behavior_gate_ok": False,
                "closure_ok": False,
                "checks": [
                    {
                        "id": "behavior.coverage.B001",
                        "status": "fail",
                        "message": "no valid behavior case maps this public clause",
                        "evidence": {"public_text": "wildcard doubles its argument"},
                    }
                ],
            }

            prompt = prepare_repair_workspace(
                workspace, check_result=result, task_markdown="# Demo"
            )
            report = (workspace / "CONTRACT_CLOSURE_FAILURES.md").read_text()

            self.assertIn("wildcard doubles its argument", report)
            self.assertIn("P3 — evidence quality (non-repairing)", report)
            self.assertNotIn("Machine-readable report", report)
            self.assertIn("Do not inspect `flb-contract-check`", prompt)

    def test_audit_aggregates_primary_and_repair_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = write_contract_closure_audit(
                tmp,
                initial={"closure_ok": False},
                final={"closure_ok": True},
                repair_rounds_used=1,
                agent_primary={
                    "passed": False,
                    "duration_seconds": 4.5,
                    "usage": {
                        "api_calls": 3,
                        "total_tokens": 100,
                        "prompt_cache_hit_tokens": 60,
                        "prompt_cache_miss_tokens": 20,
                        "effective_uncached_prompt_tokens": 20,
                    },
                },
                agent_repair={
                    "passed": True,
                    "duration_seconds": 1.5,
                    "usage": {
                        "api_calls": 2,
                        "total_tokens": 40,
                        "prompt_cache_hit_tokens": 10,
                        "prompt_cache_miss_tokens": 10,
                        "effective_uncached_prompt_tokens": 10,
                    },
                },
            )

            self.assertEqual(payload["usage_totals"]["api_calls"], 5)
            self.assertEqual(payload["usage_totals"]["total_tokens"], 140)
            self.assertEqual(payload["usage_totals"]["duration_seconds"], 6.0)
            self.assertEqual(payload["usage_totals"]["prompt_cache_hit_tokens"], 70)
            self.assertEqual(payload["usage_totals"]["prompt_cache_miss_tokens"], 30)
            self.assertEqual(payload["usage_totals"]["prompt_cache_hit_rate"], 0.7)
            self.assertEqual(len(payload["usage_totals"]["phases"]), 2)

    def test_runner_repairs_once_and_evaluates_even_when_final_gate_is_open(
        self,
    ) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        open_result = {
            "schema_version": "featureliftbench.contract_closure_check.v1",
            "checker_version": "contract_closure_gate.v1",
            "hard_gate_ok": False,
            "behavior_gate_ok": False,
            "closure_ok": False,
            "repair_needed": True,
            "summary": {"pass": 0, "fail": 1, "unknown": 0},
            "hard_failure_count": 1,
            "soft_open_count": 0,
            "unknown_count": 0,
            "checks": [
                {
                    "id": "api.featurelifted.missing",
                    "category": "api",
                    "status": "fail",
                    "severity": "hard",
                    "message": "missing API",
                }
            ],
        }
        configs = []

        def fake_run(context, config, **_kwargs):
            configs.append(config)
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=123,
                duration_seconds=0.01,
                stdout="",
                stderr="",
                reason="step limit exceeded",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        evaluation = {
            "status": "passed",
            "scores": {"functional_gate": 1.0},
            "functional_pass": True,
        }
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter", return_value=adapter
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                side_effect=[dict(open_result), dict(open_result)],
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value=evaluation,
            ) as evaluator,
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(contract_closure_gate=True).to_env(),
                    timeout_seconds=1200,
                ),
            )
            self.assertEqual(result["status"], "passed")
            self.assertFalse(result["agent"]["passed"])
            self.assertEqual(adapter.run.call_count, 2)
            self.assertEqual(checker.call_count, 2)
            evaluator.assert_called_once()
            self.assertEqual(result["contract_closure"]["repair_rounds_used"], 1)
            self.assertFalse(result["contract_closure"]["final"]["closure_ok"])
            self.assertEqual(configs[1].timeout_seconds, 900)
            self.assertEqual(
                configs[1].env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"], "20"
            )
            self.assertTrue((output / "contract_closure_initial.json").is_file())
            self.assertTrue((output / "contract_closure_final.json").is_file())
            self.assertTrue((output / "contract_closure_phase.json").is_file())
            self.assertTrue(
                (output / "workspace" / "CONTRACT_CLOSURE_FAILURES.md").is_file()
            )

    def test_lite_runner_uses_structure_only_and_separate_phase_budgets(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        failed = {
            "hard_gate_ok": False,
            "behavior_gate_ok": True,
            "closure_ok": False,
            "repair_needed": True,
            "summary": {"pass": 0, "fail": 1, "unknown": 0},
            "hard_failure_count": 1,
            "soft_open_count": 0,
            "unknown_count": 0,
            "checks": [
                {
                    "id": "api.featurelifted.missing",
                    "category": "api",
                    "status": "fail",
                    "severity": "hard",
                    "message": "missing API",
                }
            ],
        }
        configs = []

        def fake_run(context, config, **_kwargs):
            configs.append(config)
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=0,
                duration_seconds=0.01,
                stdout="",
                stderr="",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter", return_value=adapter
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                side_effect=[dict(failed), dict(failed)],
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "passed",
                    "scores": {"functional_gate": 1.0},
                    "functional_pass": True,
                },
            ) as evaluator,
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(contract_closure_gate_lite=True).to_env(),
                    timeout_seconds=1200,
                ),
            )
            workspace_has_cases = (output / "workspace" / "contract_cases").exists()
            repair_task = (output / "workspace" / "TASK.md").read_text(
                encoding="utf-8"
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["contract_closure"]["arm"], "contract_closure_gate_lite")
        self.assertEqual(adapter.run.call_count, 2)
        evaluator.assert_called_once()
        self.assertTrue(
            all(call.kwargs["check_mode"] == "structure" for call in checker.call_args_list)
        )
        self.assertEqual(
            configs[0].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "2000000",
        )
        self.assertEqual(configs[0].env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"], "45")
        self.assertEqual(
            configs[1].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "200000",
        )
        self.assertEqual(configs[1].env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"], "5")
        self.assertFalse(workspace_has_cases)
        self.assertIn("Repair (Lite)", repair_task)
        self.assertIn("--structure-only --summary", repair_task)

    def test_lite_v1_frozen_runner_preserves_pilot_prompt_and_repair_budget(
        self,
    ) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        failed = {
            "hard_gate_ok": False,
            "behavior_gate_ok": True,
            "closure_ok": False,
            "repair_needed": True,
            "summary": {"pass": 0, "fail": 4, "unknown": 0},
            "hard_failure_count": 4,
            "soft_open_count": 0,
            "unknown_count": 0,
            "checks": [
                {
                    "id": f"api.featurelifted.missing_{index}",
                    "category": "api",
                    "status": "fail",
                    "severity": "hard",
                    "message": "missing API",
                }
                for index in range(4)
            ],
        }
        configs = []

        def fake_run(context, config, **_kwargs):
            configs.append(config)
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=0,
                duration_seconds=0.01,
                stdout="",
                stderr="",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter", return_value=adapter
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                side_effect=[dict(failed), dict(failed)],
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "passed",
                    "scores": {"functional_gate": 1.0},
                    "functional_pass": True,
                },
            ) as evaluator,
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(
                        contract_closure_gate_lite_v1=True
                    ).to_env(),
                    timeout_seconds=1200,
                ),
            )
            repair_task = (output / "workspace" / "TASK.md").read_text(
                encoding="utf-8"
            )

        closure = result["contract_closure"]
        self.assertEqual(result["status"], "passed")
        self.assertEqual(closure["arm"], "contract_closure_gate_lite_v1_frozen")
        self.assertEqual(adapter.run.call_count, 2)
        evaluator.assert_called_once()
        self.assertTrue(
            all(call.kwargs["check_mode"] == "structure" for call in checker.call_args_list)
        )
        self.assertTrue(closure["repair_decision"]["eligible"])
        self.assertEqual(
            closure["repair_decision"]["policy_version"],
            "contract_closure_gate_lite.v1-frozen.1",
        )
        self.assertEqual(
            configs[0].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "2000000",
        )
        self.assertEqual(
            configs[1].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "500000",
        )
        self.assertEqual(configs[1].env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"], "10")
        self.assertEqual(
            configs[1].env[
                "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_LITE_V1_FROZEN"
            ],
            "1",
        )
        self.assertIn("## Public Contract Closure Gate Lite", repair_task)
        self.assertNotIn("Gate Lite V2", repair_task)
        self.assertIn("Repair (Lite)", repair_task)
        self.assertNotIn("roughly the first 6 agent steps", repair_task)

    def test_lite_rescue_runner_uses_v1_prompt_and_selective_budget(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        failed = {
            "hard_gate_ok": False,
            "behavior_gate_ok": True,
            "closure_ok": False,
            "repair_needed": True,
            "summary": {"pass": 0, "fail": 1, "unknown": 0},
            "hard_failure_count": 1,
            "soft_open_count": 0,
            "unknown_count": 0,
            "checks": [
                {
                    "id": "api.featurelifted.missing",
                    "category": "api",
                    "status": "fail",
                    "severity": "hard",
                    "message": "missing API",
                }
            ],
        }
        configs = []

        def fake_run(context, config, **_kwargs):
            configs.append(config)
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=0,
                duration_seconds=0.01,
                stdout="",
                stderr="",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter", return_value=adapter
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                side_effect=[dict(failed), dict(failed)],
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "passed",
                    "scores": {"functional_gate": 1.0},
                    "functional_pass": True,
                },
            ),
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(
                        contract_closure_gate_lite_rescue=True
                    ).to_env(),
                    timeout_seconds=1200,
                ),
            )
            repair_task = (output / "workspace" / "TASK.md").read_text(
                encoding="utf-8"
            )

        closure = result["contract_closure"]
        self.assertEqual(closure["arm"], "contract_closure_gate_lite_rescue")
        self.assertEqual(adapter.run.call_count, 2)
        self.assertTrue(
            all(
                call.kwargs["check_mode"] == "structure"
                for call in checker.call_args_list
            )
        )
        self.assertEqual(
            closure["repair_decision"]["policy_version"],
            "contract_closure_gate_lite_rescue.v1",
        )
        self.assertTrue(closure["repair_decision"]["eligible"])
        self.assertEqual(
            configs[1].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "200000",
        )
        self.assertEqual(
            configs[1].env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"], "5"
        )
        self.assertEqual(
            configs[1].env[
                "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_LITE_RESCUE"
            ],
            "1",
        )
        self.assertIn("## Public Contract Closure Gate Lite Rescue", repair_task)
        self.assertNotIn("Gate Lite V2", repair_task)
        self.assertNotIn("roughly the first 6 agent steps", repair_task)

    def test_v3_runner_uses_micro_checks_and_repairs_behavior_mismatch(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        mismatch = {
            "hard_gate_ok": True,
            "behavior_gate_ok": False,
            "closure_ok": False,
            "repair_needed": True,
            "summary": {"pass": 1, "fail": 1, "unknown": 0},
            "hard_failure_count": 0,
            "soft_open_count": 1,
            "actionable_behavior_failure_count": 1,
            "unknown_count": 0,
            "checks": [
                {
                    "id": "behavior.case.edge",
                    "category": "behavior",
                    "status": "fail",
                    "severity": "soft",
                    "message": "direct assertion failed: AssertionError",
                }
            ],
        }
        closed = {
            **mismatch,
            "behavior_gate_ok": True,
            "closure_ok": True,
            "repair_needed": False,
            "summary": {"pass": 2, "fail": 0, "unknown": 0},
            "soft_open_count": 0,
            "actionable_behavior_failure_count": 0,
            "checks": [],
        }
        configs = []

        def fake_run(context, config, **_kwargs):
            configs.append(config)
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=0,
                duration_seconds=0.01,
                stdout="",
                stderr="",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter", return_value=adapter
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                side_effect=[dict(mismatch), dict(closed)],
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "passed",
                    "scores": {"functional_gate": 1.0},
                    "functional_pass": True,
                },
            ) as evaluator,
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(contract_closure_gate_v3=True).to_env(),
                    timeout_seconds=1200,
                ),
            )
            repair_task = (output / "workspace" / "TASK.md").read_text(
                encoding="utf-8"
            )
            cases_readme = (
                output / "workspace" / "contract_cases" / "README.md"
            ).read_text(encoding="utf-8")

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["contract_closure"]["arm"], "contract_closure_gate_v3")
        self.assertEqual(adapter.run.call_count, 2)
        evaluator.assert_called_once()
        self.assertTrue(
            all(call.kwargs["check_mode"] == "micro" for call in checker.call_args_list)
        )
        self.assertEqual(
            configs[0].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "2000000",
        )
        self.assertEqual(
            configs[1].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "200000",
        )
        self.assertEqual(configs[1].env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"], "5")
        self.assertEqual(
            configs[1].env["FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_V3"], "1"
        )
        self.assertIn("Repair (V3)", repair_task)
        self.assertIn("--micro --summary", repair_task)
        self.assertIn("exactly two", cases_readme)

    def test_lite_rescue_plus_runner_uses_bounded_behavior_repair(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        mismatch = {
            "hard_gate_ok": True,
            "behavior_gate_ok": False,
            "closure_ok": False,
            "repair_needed": True,
            "summary": {"pass": 1, "fail": 1, "unknown": 0},
            "hard_failure_count": 0,
            "soft_open_count": 1,
            "actionable_behavior_failure_count": 1,
            "unknown_count": 0,
            "checks": [
                {
                    "id": "behavior.case.composed",
                    "category": "behavior",
                    "status": "fail",
                    "severity": "soft",
                    "message": "direct assertion failed: AssertionError",
                    "evidence": {
                        "mode": "direct",
                        "public_witness": True,
                        "behavior_ids": ["B002"],
                    },
                }
            ],
        }
        closed = {
            **mismatch,
            "behavior_gate_ok": True,
            "closure_ok": True,
            "repair_needed": False,
            "checks": [],
        }
        configs = []

        def fake_run(context, config, **_kwargs):
            configs.append(config)
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=0,
                duration_seconds=0.01,
                stdout="",
                stderr="",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter",
                return_value=adapter,
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                side_effect=[dict(mismatch), dict(closed)],
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "passed",
                    "scores": {"functional_gate": 1.0},
                    "functional_pass": True,
                },
            ),
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(
                        contract_closure_gate_lite_rescue_plus=True
                    ).to_env(),
                    timeout_seconds=1200,
                ),
            )
            repair_task = (output / "workspace" / "TASK.md").read_text(
                encoding="utf-8"
            )

        closure = result["contract_closure"]
        self.assertEqual(closure["arm"], "contract_closure_gate_lite_rescue_plus")
        self.assertEqual(adapter.run.call_count, 2)
        self.assertTrue(
            all(
                call.kwargs["check_mode"] == "lite_plus"
                for call in checker.call_args_list
            )
        )
        self.assertEqual(
            closure["repair_decision"]["policy_version"],
            "contract_closure_gate_lite_rescue_plus.v2.2",
        )
        self.assertEqual(closure["repair_kind"], "defect_repair")
        self.assertEqual(closure["defect_repair_rounds_used"], 1)
        self.assertEqual(closure["evidence_completion_rounds_used"], 0)
        self.assertEqual(
            configs[1].env[
                "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS"
            ],
            "1",
        )
        self.assertEqual(
            configs[1].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "200000",
        )
        self.assertEqual(
            configs[1].env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"],
            "5",
        )
        self.assertIn("Targeted Public-Contract Defect Repair", repair_task)
        self.assertIn("--lite-plus --summary", repair_task)
        self.assertNotIn("first tool action must write", repair_task)
        self.assertIn("reserved for an implementation defect", repair_task)
        self.assertIn("PUBLIC_CONTRACT.json", repair_task)

    def test_lite_rescue_plus_missing_witness_skips_paid_repair(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        missing_smoke = {
            "hard_gate_ok": True,
            "behavior_gate_ok": False,
            "closure_ok": False,
            "repair_needed": False,
            "summary": {"pass": 1, "fail": 1, "unknown": 0},
            "hard_failure_count": 0,
            "soft_open_count": 1,
            "actionable_behavior_failure_count": 0,
            "unknown_count": 0,
            "checks": [
                {
                    "id": "behavior.witness.required",
                    "category": "behavior_evidence",
                    "status": "fail",
                    "severity": "soft",
                    "message": (
                        "no valid executable direct case was provided for the selected witness"
                    ),
                }
            ],
        }
        configs = []

        def fake_run(context, config, **_kwargs):
            configs.append(config)
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=0,
                duration_seconds=0.01,
                stdout="",
                stderr="",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter",
                return_value=adapter,
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                return_value=dict(missing_smoke),
            ),
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "passed",
                    "scores": {"functional_gate": 1.0},
                    "functional_pass": True,
                },
            ),
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(
                        contract_closure_gate_lite_rescue_plus=True
                    ).to_env(),
                    timeout_seconds=1200,
                ),
            )
            final_submission = (
                output
                / "workspace"
                / "submission"
                / "featurelifted"
                / "__init__.py"
            ).read_text(encoding="utf-8")

        closure = result["contract_closure"]
        self.assertEqual(final_submission, "VALUE = 1\n")
        self.assertEqual(adapter.run.call_count, 1)
        self.assertEqual(closure["repair_kind"], "none")
        self.assertEqual(closure["evidence_completion_rounds_used"], 0)
        self.assertEqual(closure["defect_repair_rounds_used"], 0)
        self.assertFalse(closure["functional_rescue_candidate"])
        self.assertIn("telemetry only", closure["repair_decision"]["reason"])
        self.assertFalse((output / "agent_repair").exists())

    def test_lite_v2_runner_skips_broad_repair_and_records_decision(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        broad = {
            "hard_gate_ok": False,
            "behavior_gate_ok": True,
            "closure_ok": False,
            "repair_needed": True,
            "summary": {"pass": 0, "fail": 4, "unknown": 0},
            "hard_failure_count": 4,
            "soft_open_count": 0,
            "unknown_count": 0,
            "checks": [
                {
                    "id": f"api.featurelifted.missing_{index}",
                    "category": "api",
                    "status": "fail",
                    "severity": "hard",
                    "message": "missing API",
                }
                for index in range(4)
            ],
        }

        def fake_run(context, config, **_kwargs):
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=0,
                duration_seconds=0.01,
                stdout="",
                stderr="",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter", return_value=adapter
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                return_value=dict(broad),
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "failed",
                    "scores": {"functional_gate": 0.0},
                    "functional_pass": False,
                },
            ) as evaluator,
        ):
            result = run_agent_on_task(
                task_dir,
                Path(tmp) / "output",
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(contract_closure_gate_lite=True).to_env(),
                    timeout_seconds=1200,
                ),
            )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(adapter.run.call_count, 1)
        self.assertEqual(checker.call_count, 1)
        evaluator.assert_called_once()
        closure = result["contract_closure"]
        self.assertFalse(closure["repair_triggered"])
        self.assertFalse(closure["repair_decision"]["eligible"])
        self.assertIn("exceed", closure["repair_decision"]["reason"])

    def test_lite_v21_retries_one_early_tool_validation_failure(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        closed = {
            "hard_gate_ok": True,
            "behavior_gate_ok": True,
            "closure_ok": True,
            "repair_needed": False,
            "summary": {"pass": 1, "fail": 0, "unknown": 0},
            "hard_failure_count": 0,
            "soft_open_count": 0,
            "unknown_count": 0,
            "checks": [],
        }
        calls = 0

        def fake_run(context, config, **_kwargs):
            nonlocal calls
            calls += 1
            context.agent_output_dir.mkdir(parents=True, exist_ok=True)
            if calls == 1:
                (context.agent_output_dir / "usage.json").write_text(
                    json.dumps(
                        {
                            "available": True,
                            "assistant_steps": 4,
                            "api_calls": 4,
                            "total_tokens": 100,
                            "exit_status": "tool_validation_error",
                            "infrastructure_error": {
                                "failure_class": "tool_validation_error",
                                "retryable": True,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return AgentCommandResult(
                    name=config.agent,
                    command=[config.agent],
                    report_command=[config.agent],
                    returncode=86,
                    duration_seconds=0.01,
                    stdout="",
                    stderr="",
                    reason="tool validation error",
                )

            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            (context.agent_output_dir / "usage.json").write_text(
                json.dumps(
                    {
                        "available": True,
                        "assistant_steps": 3,
                        "api_calls": 3,
                        "total_tokens": 200,
                        "exit_status": "passed",
                    }
                ),
                encoding="utf-8",
            )
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=0,
                duration_seconds=0.02,
                stdout="created submission",
                stderr="",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter", return_value=adapter
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated",
                return_value=dict(closed),
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "passed",
                    "scores": {"functional_gate": 1.0},
                    "functional_pass": True,
                },
            ) as evaluator,
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(contract_closure_gate_lite=True).to_env(),
                    timeout_seconds=1200,
                ),
            )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(adapter.run.call_count, 2)
            checker.assert_called_once()
            evaluator.assert_called_once()
            retry = result["contract_closure"]["infrastructure_retry"]
            self.assertTrue(retry["eligible"])
            self.assertEqual(retry["attempts_used"], 1)
            self.assertEqual(retry["retry_exit_status"], "passed")
            self.assertTrue((output / "agent_primary_attempt1" / "usage.json").is_file())
            self.assertEqual(
                len(result["contract_closure"]["agent_primary_attempts"]), 2
            )
            self.assertEqual(
                result["contract_closure"]["usage_totals"]["total_tokens"], 300
            )

    def test_lite_v21_does_not_retry_normal_step_exhaustion(self) -> None:
        from featureliftbench.agent_runner import (
            _contract_closure_infrastructure_retry_decision,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agent_dir = root / "agent"
            submission = root / "submission"
            agent_dir.mkdir()
            submission.mkdir()
            (agent_dir / "usage.json").write_text(
                json.dumps(
                    {
                        "available": True,
                        "assistant_steps": 45,
                        "exit_status": "step_limit_exceeded",
                    }
                ),
                encoding="utf-8",
            )
            result = AgentCommandResult(
                name="openhands-agent",
                command=[],
                report_command=[],
                returncode=123,
                duration_seconds=1.0,
                stdout="",
                stderr="",
            )

            decision = _contract_closure_infrastructure_retry_decision(
                agent_result=result,
                agent_output_dir=agent_dir,
                submission_dir=submission,
                enabled=True,
                retry_limit=1,
                max_trigger_steps=8,
                policy_version="contract_closure_gate_lite.v2.1",
            )

            self.assertFalse(decision["requested"])
            self.assertFalse(decision["eligible"])

    def test_budget_control_uses_same_primary_limits_without_checker(self) -> None:
        task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "tasks"
            / "sqlparse__token_tree_core__001"
        )
        configs = []

        def fake_run(context, config, **_kwargs):
            configs.append(config)
            package = context.submission_dir / "featurelifted"
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            return AgentCommandResult(
                name=config.agent,
                command=[config.agent],
                report_command=[config.agent],
                returncode=123,
                duration_seconds=0.01,
                stdout="",
                stderr="",
                reason="step limit exceeded",
            )

        adapter = mock.MagicMock()
        adapter.run.side_effect = fake_run
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch(
                "featureliftbench.agent_runner.get_agent_adapter", return_value=adapter
            ),
            mock.patch(
                "featureliftbench.contract_closure_gate.check_workspace_isolated"
            ) as checker,
            mock.patch(
                "featureliftbench.agent_runner._evaluate_collected_submission",
                return_value={
                    "status": "passed",
                    "scores": {"functional_gate": 1.0},
                    "functional_pass": True,
                },
            ) as evaluator,
        ):
            output = Path(tmp) / "output"
            result = run_agent_on_task(
                task_dir,
                output,
                AgentRunConfig(
                    agent="command",
                    env=AblationOptions(
                        contract_closure_budget_control=True
                    ).to_env(),
                ),
            )
            workspace = output / "workspace"
            control_task = (workspace / "TASK.md").read_text(encoding="utf-8")
            leaked_gate_files = any(
                (workspace / name).exists()
                for name in (
                    "PUBLIC_CONTRACT.json",
                    "contract_cases",
                    "flb-contract-check",
                )
            )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(adapter.run.call_count, 1)
        checker.assert_not_called()
        evaluator.assert_called_once()
        self.assertFalse(leaked_gate_files)
        self.assertIn("Equal-Budget Implementation Review", control_task)
        self.assertEqual(
            configs[0].env["FEATURELIFTBENCH_OPENHANDS_TOTAL_TOKEN_LIMIT"],
            "2000000",
        )
        self.assertEqual(configs[0].env["FEATURELIFTBENCH_OPENHANDS_MAX_STEPS"], "45")


if __name__ == "__main__":
    unittest.main()
