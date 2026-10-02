"""Unit tests for Test-First Lift freeze/verify (P0)."""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from featureliftbench.ablation import AblationOptions
from featureliftbench.ablation import resolve_ablation_options
from featureliftbench.test_first_lift.audit import compute_method_freeze
from featureliftbench.test_first_lift.audit import write_phase_audit
from featureliftbench.test_first_lift.freeze import compute_characterization_lock
from featureliftbench.test_first_lift.freeze import freeze_characterization
from featureliftbench.test_first_lift.freeze import verify_characterization
from featureliftbench.test_first_lift.freeze import verify_characterization_frozen
from featureliftbench.test_first_lift.workspace import install_test_first_lift_workspace


def _write_case(
    root: Path,
    *,
    case_id: str = "answer",
    required: str = "featurelifted.answer",
    upstream_value: int = 7,
) -> Path:
    case = root / "characterization" / f"case_{case_id}.py"
    case.write_text(
        textwrap.dedent(
            f"""\
            CASE_ID = {case_id!r}
            TASK_CLAUSE = "B001"
            REQUIRED_API = [{required!r}]

            def run_upstream():
                import demo
                return {{"result": {upstream_value}, "exception": None, "state_after": None}}

            def run_featurelifted():
                import featurelifted
                return {{
                    "result": featurelifted.answer(),
                    "exception": None,
                    "state_after": None,
                }}
            """
        ),
        encoding="utf-8",
    )
    return case


def _prep_workspace(
    root: Path,
    *,
    required_api: list[str] | None = None,
    upstream_value: int = 7,
) -> None:
    paths = required_api or ["featurelifted.answer"]
    install_test_first_lift_workspace(root, required_api_paths=paths)
    (root / "repo").mkdir(exist_ok=True)
    (root / "repo" / "demo.py").write_text(f"VALUE = {upstream_value}\n", encoding="utf-8")
    (root / "metadata.json").write_text("{}", encoding="utf-8")


class TestFirstLiftAblationTests(unittest.TestCase):
    def test_arm_name(self) -> None:
        self.assertEqual(
            AblationOptions(test_first_lift=True).ablation_arm, "test_first_lift"
        )

    def test_mutually_exclusive(self) -> None:
        with self.assertRaises(ValueError):
            AblationOptions(td_cognition=True, test_first_lift=True)
        with self.assertRaises(ValueError):
            AblationOptions(self_contract=True, test_first_lift=True)

    def test_resolve_from_profile(self) -> None:
        options = resolve_ablation_options(profile={"test_first_lift": True})
        self.assertTrue(options.test_first_lift)
        self.assertEqual(options.ablation_arm, "test_first_lift")


class TestFirstLiftFreezeTests(unittest.TestCase):
    def test_freeze_verify_and_case_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _prep_workspace(root)
            _write_case(root)
            frozen = freeze_characterization(root)
            self.assertTrue(frozen.get("ok"), frozen)
            self.assertEqual(frozen.get("lock_schema"), "v2")
            self.assertTrue((root / "oracle.json").is_file())
            self.assertTrue((root / "characterization.lock").is_file())
            # Phase B starts empty.
            self.assertTrue(frozen.get("submission_cleared"))
            self.assertTrue((root / "submission").is_dir())
            self.assertFalse(any((root / "submission").rglob("*")))

            pkg = root / "submission" / "featurelifted"
            pkg.mkdir(parents=True)
            (pkg / "__init__.py").write_text(
                "def answer():\n    return 7\n",
                encoding="utf-8",
            )
            verified = verify_characterization(root)
            self.assertTrue(verified.get("ok"), verified)
            self.assertTrue(verified.get("characterization_pass"))

            case = root / "characterization" / "case_answer.py"
            case.write_text(case.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
            check = verify_characterization_frozen(root)
            self.assertFalse(check.get("ok"))

    def test_oracle_tamper_detected_by_v2_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _prep_workspace(root)
            _write_case(root)
            frozen = freeze_characterization(root)
            self.assertTrue(frozen.get("ok"), frozen)
            oracle = root / "oracle.json"
            payload = json.loads(oracle.read_text(encoding="utf-8"))
            # Mutate a frozen observation.
            first_id = next(iter(payload["cases"]))
            payload["cases"][first_id]["observation"]["result"] = 999
            oracle.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            check = verify_characterization_frozen(root)
            self.assertFalse(check.get("ok"), check)
            self.assertIn("mismatch", str(check.get("error") or "").lower())

    def test_legacy_lock_still_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _prep_workspace(root)
            _write_case(root)
            frozen = freeze_characterization(root)
            self.assertTrue(frozen.get("ok"), frozen)
            current = compute_characterization_lock(root)
            legacy = current["legacy_characterization_lock"]
            (root / "characterization.lock").write_text(legacy + "\n", encoding="utf-8")
            check = verify_characterization_frozen(root)
            self.assertTrue(check.get("ok"), check)
            self.assertEqual(check.get("lock_schema"), "legacy")

            # Oracle tamper still leaves legacy lock green (documented limitation).
            oracle = root / "oracle.json"
            payload = json.loads(oracle.read_text(encoding="utf-8"))
            first_id = next(iter(payload["cases"]))
            payload["cases"][first_id]["observation"]["result"] = 42
            oracle.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            check2 = verify_characterization_frozen(root)
            self.assertTrue(check2.get("ok"), check2)
            self.assertEqual(check2.get("lock_schema"), "legacy")

    def test_freeze_rejects_vacuous_cases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_test_first_lift_workspace(root)
            (root / "repo").mkdir()
            (root / "metadata.json").write_text("{}", encoding="utf-8")
            case = root / "characterization" / "case_const.py"
            case.write_text(
                textwrap.dedent(
                    """\
                    CASE_ID = "const"
                    TASK_CLAUSE = "B001"
                    REQUIRED_API = ["featurelifted.x"]

                    def run_upstream():
                        return {"result": 1, "exception": None, "state_after": None}

                    def run_featurelifted():
                        return {"result": 1, "exception": None, "state_after": None}
                    """
                ),
                encoding="utf-8",
            )
            frozen = freeze_characterization(root)
            self.assertFalse(frozen.get("ok"), frozen)
            self.assertIn("vacuous", " ".join(frozen.get("errors") or []).lower())

    def test_per_case_stub_required_not_any(self) -> None:
        """If one case is vacuous even when another fails stub, freeze fails."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _prep_workspace(root, required_api=["featurelifted.answer", "featurelifted.other"])
            _write_case(root, case_id="good", required="featurelifted.answer")
            # Vacuous: run_featurelifted returns fixed upstream value without calling package.
            vac = root / "characterization" / "case_vacuous.py"
            vac.write_text(
                textwrap.dedent(
                    """\
                    CASE_ID = "vacuous"
                    TASK_CLAUSE = "B001"
                    REQUIRED_API = ["featurelifted.other"]

                    def run_upstream():
                        return {"result": 7, "exception": None, "state_after": None}

                    def run_featurelifted():
                        return {"result": 7, "exception": None, "state_after": None}
                    """
                ),
                encoding="utf-8",
            )
            frozen = freeze_characterization(root)
            self.assertFalse(frozen.get("ok"), frozen)
            self.assertIn("vacuous", frozen.get("vacuous_cases") or [])

    def test_flaky_upstream_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _prep_workspace(root)
            marker = root / "flaky_marker"
            case = root / "characterization" / "case_flaky.py"
            case.write_text(
                textwrap.dedent(
                    f"""\
                    CASE_ID = "flaky"
                    TASK_CLAUSE = "B001"
                    REQUIRED_API = ["featurelifted.answer"]

                    def run_upstream():
                        import os
                        marker = {str(marker)!r}
                        if os.path.exists(marker):
                            os.remove(marker)
                            return {{"result": 2, "exception": None, "state_after": None}}
                        open(marker, "w").close()
                        return {{"result": 1, "exception": None, "state_after": None}}

                    def run_featurelifted():
                        import featurelifted
                        return {{
                            "result": featurelifted.answer(),
                            "exception": None,
                            "state_after": None,
                        }}
                    """
                ),
                encoding="utf-8",
            )
            frozen = freeze_characterization(root)
            self.assertFalse(frozen.get("ok"), frozen)
            joined = " ".join(frozen.get("errors") or []).lower()
            self.assertTrue("stable" in joined or "not stable" in joined, frozen)

    def test_required_api_missing_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_test_first_lift_workspace(
                root,
                required_api_paths=["featurelifted.answer", "featurelifted.missing"],
            )
            (root / "repo").mkdir()
            (root / "repo" / "demo.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "metadata.json").write_text("{}", encoding="utf-8")
            _write_case(root, required="featurelifted.answer", upstream_value=1)
            frozen = freeze_characterization(root)
            self.assertFalse(frozen.get("ok"), frozen)
            joined = " ".join(frozen.get("errors") or [])
            self.assertIn("Required API", joined)
            self.assertIn("featurelifted.missing", joined)

    def test_freeze_clears_preexisting_submission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _prep_workspace(root)
            _write_case(root)
            sneak = root / "submission" / "featurelifted"
            sneak.mkdir(parents=True)
            (sneak / "__init__.py").write_text(
                "def answer():\n    return 7\n",
                encoding="utf-8",
            )
            frozen = freeze_characterization(root)
            self.assertTrue(frozen.get("ok"), frozen)
            self.assertFalse(any((root / "submission").rglob("*.py")))

    def test_phase_audit_separates_formal_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "out"
            ws = root / "ws"
            ws.mkdir()
            _prep_workspace(ws)
            _write_case(ws)
            self.assertTrue(freeze_characterization(ws).get("ok"))
            # No submission → formal not evaluated, but still in denominator.
            payload = write_phase_audit(
                out,
                workspace_dir=ws,
                evaluation=None,
                submission_exists=False,
            )
            self.assertTrue(payload["freeze_success"])
            self.assertFalse(payload["characterization_pass"])
            self.assertIsNone(payload["formal_functional"])
            self.assertFalse(payload["formal_evaluated"])
            self.assertTrue(payload["included_in_suite_denominator"])
            self.assertEqual(
                payload["metrics_separated"]["freeze_success"],
                payload["freeze_success"],
            )

            # With formal eval payload present.
            payload2 = write_phase_audit(
                out,
                workspace_dir=ws,
                evaluation={
                    "status": "failed",
                    "scores": {"functional_gate": 0.0},
                    "functional_pass": False,
                },
                submission_exists=True,
            )
            self.assertTrue(payload2["formal_evaluated"])
            self.assertFalse(payload2["formal_functional"])
            self.assertEqual(payload2["formal_functional_gate"], 0.0)
            freeze_meta = compute_method_freeze()
            self.assertIn("tfl_package_tree_sha256", freeze_meta)
            self.assertEqual(
                payload2["method_freeze"]["tfl_package_tree_sha256"],
                freeze_meta["tfl_package_tree_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
