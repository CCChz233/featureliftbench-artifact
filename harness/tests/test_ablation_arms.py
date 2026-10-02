"""Tests for No-Hint Main and explicit FeatureLiftBench ablation arms."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.ablation import AblationOptions
from featureliftbench.ablation import resolve_ablation_options
from featureliftbench.agent_runner import build_task_prompt
from featureliftbench.agent_runner import prepare_agent_workspace
from featureliftbench.agent_runner import redact_task_metadata
from featureliftbench.metadata import load_metadata
from featureliftbench.openhands_runner import OpenHandsRunnerConfig
from featureliftbench.openhands_runner import _build_openhands_prompt
from featureliftbench.task_render import render_agent_workspace_task


class AblationOptionsTests(unittest.TestCase):
    def test_arm_names(self) -> None:
        self.assertEqual(AblationOptions().ablation_arm, "main")
        self.assertEqual(
            AblationOptions(mount_public_tests=True).ablation_arm,
            "public_feedback",
        )
        self.assertEqual(
            AblationOptions(prompt_style="short").ablation_arm,
            "short_prompt",
        )
        self.assertEqual(
            AblationOptions(mount_public_tests=True, prompt_style="short").ablation_arm,
            "public_feedback_short_prompt",
        )
        self.assertEqual(
            AblationOptions(expose_source_hints=True).ablation_arm,
            "entrypoint_hint",
        )
        self.assertEqual(
            AblationOptions(contract_closure_gate=True).ablation_arm,
            "contract_closure_gate",
        )
        self.assertEqual(
            AblationOptions(contract_closure_gate_lite=True).ablation_arm,
            "contract_closure_gate_lite",
        )
        self.assertEqual(
            AblationOptions(contract_closure_gate_lite_v1=True).ablation_arm,
            "contract_closure_gate_lite_v1_frozen",
        )
        self.assertEqual(
            AblationOptions(contract_closure_gate_lite_rescue=True).ablation_arm,
            "contract_closure_gate_lite_rescue",
        )
        self.assertEqual(
            AblationOptions(
                contract_closure_gate_lite_rescue_plus=True
            ).ablation_arm,
            "contract_closure_gate_lite_rescue_plus",
        )
        self.assertEqual(
            AblationOptions(contract_closure_gate_v3=True).ablation_arm,
            "contract_closure_gate_v3",
        )
        self.assertEqual(
            AblationOptions(contract_closure_budget_control=True).ablation_arm,
            "contract_closure_budget_control",
        )
        self.assertEqual(
            AblationOptions(adaptive_budget_v2=True).ablation_arm,
            "adaptive_budget_v2",
        )
        self.assertEqual(
            AblationOptions(pre_submit_contract_audit=True).ablation_arm,
            "pre_submit_contract_audit",
        )
        self.assertEqual(
            AblationOptions(spec_adversarial_self_test=True).ablation_arm,
            "spec_adversarial_self_test",
        )
        self.assertEqual(
            AblationOptions(obligation_guided=True).ablation_arm,
            "obligation_guided",
        )
        self.assertEqual(
            AblationOptions(cgvl=True).ablation_arm,
            "cgvl",
        )
        self.assertEqual(
            AblationOptions(source_context="contract_only").ablation_arm,
            "contract_only",
        )
        self.assertEqual(AblationOptions().source_context, "full_repository")

    def test_contract_closure_gate_is_mutually_exclusive_with_other_methods(self) -> None:
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(contract_closure_gate=True, test_first_lift=True)
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                contract_closure_gate=True,
                contract_closure_gate_lite=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                contract_closure_gate_lite=True,
                contract_closure_budget_control=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                adaptive_budget_v2=True,
                contract_closure_gate=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                contract_closure_gate_lite=True,
                contract_closure_gate_v3=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                contract_closure_gate_lite=True,
                contract_closure_gate_lite_v1=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                contract_closure_gate_lite_v1=True,
                contract_closure_gate_lite_rescue=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                contract_closure_gate_lite_rescue=True,
                contract_closure_gate_lite_rescue_plus=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                pre_submit_contract_audit=True,
                contract_closure_gate=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                spec_adversarial_self_test=True,
                pre_submit_contract_audit=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                spec_adversarial_self_test=True,
                test_first_lift=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                obligation_guided=True,
                spec_adversarial_self_test=True,
            )
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            AblationOptions(
                cgvl=True,
                spec_adversarial_self_test=True,
            )

    def test_cli_overrides_profile(self) -> None:
        options = resolve_ablation_options(
            profile={
                "mount_public_tests": True,
                "prompt_style": "standard",
                "expose_source_hints": True,
            },
            mount_public_tests=False,
            prompt_style="short",
            expose_source_hints=False,
        )
        self.assertEqual(options.ablation_arm, "short_prompt")


class AblationWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task_dir = (
            Path(__file__).resolve().parents[2]
            / "benchmark"
            / "sanity"
            / "iniconfig__parse_config__001"
        )
        self.metadata = load_metadata(self.task_dir).data

    def test_main_hides_evaluator_tests_and_keeps_upstream_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                self.task_dir,
                workspace,
                self.metadata,
                ablation=AblationOptions(),
            )
            self.assertFalse((workspace / "public_tests").exists())
            self.assertTrue((workspace / "repo" / "testing" / "test_iniconfig.py").is_file())
            prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
            redacted = load_metadata(workspace).data
            self.assertIn("## How to work", prompt)
            self.assertIn("## Closure Discipline", prompt)
            self.assertIn("Benchmark evaluator tests", prompt)
            self.assertNotIn("Run `pytest public_tests/`", prompt)
            self.assertNotIn("Source entrypoints", prompt)
            self.assertNotIn("iniconfig.IniConfig", prompt)
            self.assertNotIn("source_entrypoints", redacted["feature"])

    def test_entrypoint_hint_is_explicit_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                self.task_dir,
                workspace,
                self.metadata,
                ablation=AblationOptions(expose_source_hints=True),
            )
            prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
            redacted = load_metadata(workspace).data
            self.assertIn("Entrypoint-Hint Ablation", prompt)
            self.assertIn("iniconfig.IniConfig", prompt)
            self.assertEqual(
                redacted["feature"]["source_entrypoints"],
                self.metadata["feature"]["source_entrypoints"],
            )

    def test_all_python_main_tasks_render_without_frozen_entrypoints(self) -> None:
        tasks_root = Path(__file__).resolve().parents[2] / "benchmark" / "tasks"
        task_dirs = sorted(
            path
            for path in tasks_root.iterdir()
            if path.is_dir() and (path / "metadata.json").is_file()
        )
        self.assertEqual(len(task_dirs), 150)
        for task_dir in task_dirs:
            with self.subTest(task_id=task_dir.name):
                metadata = load_metadata(task_dir).data
                prompt = render_agent_workspace_task(metadata)
                redacted = redact_task_metadata(metadata)
                serialized = str(redacted)
                self.assertIn("## Complete Feature Responsibility", prompt)
                self.assertIn("complete task-scoped module", prompt)
                self.assertIn("inspecting the full upstream repository", prompt)
                self.assertNotIn("source_entrypoints", serialized)
                self.assertNotIn("source_hints", serialized)
                entrypoints = set(
                    metadata.get("public_spec", {}).get("source_entrypoints", [])
                )
                entrypoints.update(
                    metadata.get("feature", {}).get("source_entrypoints", [])
                )
                for entrypoint in entrypoints:
                    self.assertNotIn(f"`{entrypoint}`", prompt)

    def test_public_feedback_mounts_public_and_mentions_pytest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                self.task_dir,
                workspace,
                self.metadata,
                ablation=AblationOptions(mount_public_tests=True),
            )
            self.assertTrue((workspace / "public_tests").is_dir())
            prompt = (workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertIn("Run `pytest public_tests/`", prompt)
            self.assertIn("Required Output API", prompt)

    def test_contract_closure_workspace_contains_only_public_contract_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = (
                Path(__file__).resolve().parents[2]
                / "benchmark"
                / "tasks"
                / "sqlparse__token_tree_core__001"
            )
            metadata = load_metadata(task_dir).data
            workspace = Path(tmp) / "ws"
            prepare_agent_workspace(
                task_dir,
                workspace,
                metadata,
                ablation=AblationOptions(contract_closure_gate=True),
            )
            self.assertTrue((workspace / "PUBLIC_CONTRACT.json").is_file())
            self.assertTrue((workspace / "contract_cases" / "README.md").is_file())
            self.assertTrue((workspace / "flb-contract-check").is_file())
            payload = (workspace / "PUBLIC_CONTRACT.json").read_text(encoding="utf-8")
            self.assertNotIn("evaluation_spec", payload)
            self.assertNotIn("hidden_test_mappings", payload)
            self.assertIn("Public Contract Closure Gate", (workspace / "TASK.md").read_text())

            lite_workspace = Path(tmp) / "lite"
            prepare_agent_workspace(
                task_dir,
                lite_workspace,
                metadata,
                ablation=AblationOptions(contract_closure_gate_lite=True),
            )
            lite_prompt = (lite_workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertTrue((lite_workspace / "PUBLIC_CONTRACT.json").is_file())
            self.assertTrue((lite_workspace / "flb-contract-check").is_file())
            self.assertFalse((lite_workspace / "contract_cases").exists())
            self.assertIn("Contract Closure Gate Lite", lite_prompt)
            self.assertIn("--structure-only --summary", lite_prompt)

            v1_workspace = Path(tmp) / "lite-v1-frozen"
            prepare_agent_workspace(
                task_dir,
                v1_workspace,
                metadata,
                ablation=AblationOptions(contract_closure_gate_lite_v1=True),
            )
            v1_prompt = (v1_workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertTrue((v1_workspace / "PUBLIC_CONTRACT.json").is_file())
            self.assertTrue((v1_workspace / "flb-contract-check").is_file())
            self.assertFalse((v1_workspace / "contract_cases").exists())
            self.assertIn("## Public Contract Closure Gate Lite", v1_prompt)
            self.assertNotIn("Gate Lite V2", v1_prompt)
            self.assertIn("Implement every Required Output API", v1_prompt)
            self.assertNotIn("roughly the first 6 agent steps", v1_prompt)

            rescue_workspace = Path(tmp) / "lite-rescue"
            prepare_agent_workspace(
                task_dir,
                rescue_workspace,
                metadata,
                ablation=AblationOptions(contract_closure_gate_lite_rescue=True),
            )
            rescue_prompt = (rescue_workspace / "TASK.md").read_text(
                encoding="utf-8"
            )
            self.assertTrue((rescue_workspace / "PUBLIC_CONTRACT.json").is_file())
            self.assertTrue((rescue_workspace / "flb-contract-check").is_file())
            self.assertFalse((rescue_workspace / "contract_cases").exists())
            self.assertIn("Public Contract Closure Gate Lite Rescue", rescue_prompt)
            self.assertIn("Implement every Required Output API", rescue_prompt)
            self.assertNotIn("Gate Lite V2", rescue_prompt)
            self.assertNotIn("roughly the first 6 agent steps", rescue_prompt)

            plus_workspace = Path(tmp) / "lite-rescue-plus"
            prepare_agent_workspace(
                task_dir,
                plus_workspace,
                metadata,
                ablation=AblationOptions(
                    contract_closure_gate_lite_rescue_plus=True
                ),
            )
            plus_prompt = (plus_workspace / "TASK.md").read_text(
                encoding="utf-8"
            )
            plus_readme = (
                plus_workspace / "contract_cases" / "README.md"
            ).read_text(encoding="utf-8")
            self.assertTrue((plus_workspace / "PUBLIC_CONTRACT.json").is_file())
            witness = plus_workspace / "PUBLIC_WITNESS.json"
            self.assertTrue(witness.is_file())
            witness_payload = witness.read_text(encoding="utf-8")
            self.assertNotIn("evaluation_spec", witness_payload)
            self.assertNotIn("hidden_test_mappings", witness_payload)
            self.assertTrue((plus_workspace / "flb-contract-check").is_file())
            self.assertIn("Lite Rescue+", plus_prompt)
            self.assertIn("--lite-plus --summary", plus_prompt)
            self.assertIn("step 32", plus_prompt)
            self.assertIn("exactly one concise direct-mode", plus_readme)
            self.assertIn("shared 60-second", plus_readme)

            v3_workspace = Path(tmp) / "v3"
            prepare_agent_workspace(
                task_dir,
                v3_workspace,
                metadata,
                ablation=AblationOptions(contract_closure_gate_v3=True),
            )
            v3_prompt = (v3_workspace / "TASK.md").read_text(encoding="utf-8")
            v3_readme = (v3_workspace / "contract_cases" / "README.md").read_text(
                encoding="utf-8"
            )
            self.assertTrue((v3_workspace / "PUBLIC_CONTRACT.json").is_file())
            self.assertTrue((v3_workspace / "flb-contract-check").is_file())
            self.assertIn("Contract Closure Gate V3", v3_prompt)
            self.assertIn("--micro --summary", v3_prompt)
            self.assertIn("exactly two", v3_readme)
            self.assertIn("Full clause coverage is not required", v3_readme)

            control_workspace = Path(tmp) / "control"
            prepare_agent_workspace(
                task_dir,
                control_workspace,
                metadata,
                ablation=AblationOptions(contract_closure_budget_control=True),
            )
            control_prompt = (control_workspace / "TASK.md").read_text(
                encoding="utf-8"
            )
            self.assertFalse((control_workspace / "PUBLIC_CONTRACT.json").exists())
            self.assertFalse((control_workspace / "contract_cases").exists())
            self.assertFalse((control_workspace / "flb-contract-check").exists())
            self.assertIn("Equal-Budget Implementation Review", control_prompt)
            self.assertIn("No contract checker", control_prompt)

            cgvl_workspace = Path(tmp) / "cgvl"
            prepare_agent_workspace(
                task_dir,
                cgvl_workspace,
                metadata,
                ablation=AblationOptions(cgvl=True),
            )
            cgvl_prompt = (cgvl_workspace / "TASK.md").read_text(encoding="utf-8")
            self.assertTrue((cgvl_workspace / "cgvl_matrix.json").is_file())
            self.assertTrue((cgvl_workspace / "run_cgvl_check.py").is_file())
            self.assertTrue((cgvl_workspace / "cgvl_cells").is_dir())
            self.assertIn("Contract-Guided Verification Loop", cgvl_prompt)
            self.assertNotIn(
                "source_entrypoints",
                (cgvl_workspace / "cgvl_matrix.json").read_text(encoding="utf-8"),
            )
            self.assertFalse((cgvl_workspace / "public_tests").exists())

            main_workspace = Path(tmp) / "main"
            prepare_agent_workspace(
                task_dir,
                main_workspace,
                metadata,
                ablation=AblationOptions(),
            )
            self.assertFalse((main_workspace / "PUBLIC_CONTRACT.json").exists())
            self.assertFalse((main_workspace / "contract_cases").exists())
            self.assertFalse((main_workspace / "flb-contract-check").exists())

    def test_short_prompt_drops_closure_keeps_api(self) -> None:
        prompt = build_task_prompt(
            self.metadata,
            ablation=AblationOptions(prompt_style="short"),
        )
        self.assertNotIn("## Closure Discipline", prompt)
        self.assertNotIn("## Entanglement Context", prompt)
        self.assertIn("## Required Output API", prompt)
        self.assertIn("## Target Feature", prompt)
        self.assertNotIn("Run `pytest public_tests/`", prompt)
        self.assertIn("Forbidden imports", prompt)

    def test_openhands_wrapper_respects_test_blind_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "TASK.md"
            task.write_text("# task\n", encoding="utf-8")
            config = OpenHandsRunnerConfig(
                workspace_dir=root,
                task_file=task,
                submission_dir=root / "submission",
                agent_output_dir=root / "agent",
                model="test-model",
            )
            with mock.patch.dict(
                "os.environ",
                {"FEATURELIFTBENCH_MOUNT_PUBLIC_TESTS": "0"},
                clear=False,
            ):
                text = _build_openhands_prompt(config)
            self.assertIn("not mounted", text)
            self.assertIn("upstream tests", text)
            self.assertNotIn("PYTHONPATH=submission pytest public_tests/", text)

    def test_openhands_lite_rescue_plus_repair_uses_targeted_prompt_verbatim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / "TASK.md"
            targeted = (
                "# FeatureLiftBench Targeted Public-Contract Repair\n\n"
                "first tool action must write contract_cases/test_public_smoke.py\n"
            )
            task.write_text(targeted, encoding="utf-8")
            config = OpenHandsRunnerConfig(
                workspace_dir=root,
                task_file=task,
                submission_dir=root / "submission",
                agent_output_dir=root / "agent",
                model="test-model",
            )
            with mock.patch.dict(
                "os.environ",
                {
                    "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS": "1",
                    "FEATURELIFTBENCH_CONTRACT_CLOSURE_PHASE": "repair",
                },
                clear=False,
            ):
                text = _build_openhands_prompt(config)

            self.assertEqual(text, targeted)
            self.assertNotIn("Create the package immediately", text)


if __name__ == "__main__":
    unittest.main()
