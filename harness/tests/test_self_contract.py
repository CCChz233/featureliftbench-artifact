"""Unit tests for Self-Authored Contract helpers."""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.ablation import AblationOptions
from featureliftbench.ablation import resolve_ablation_options
from featureliftbench.self_contract.author_gate import evaluate_author_gate
from featureliftbench.self_contract.freeze import freeze_contracts
from featureliftbench.self_contract.freeze import verify_contracts_frozen
from featureliftbench.self_contract.workspace import install_self_contract_workspace


class SelfContractAblationTests(unittest.TestCase):
    def test_arm_name(self) -> None:
        self.assertEqual(
            AblationOptions(self_contract=True).ablation_arm, "self_contract"
        )

    def test_mutually_exclusive_with_td_and_exec(self) -> None:
        with self.assertRaises(ValueError):
            AblationOptions(td_cognition=True, self_contract=True)
        with self.assertRaises(ValueError):
            AblationOptions(exec_contract=True, self_contract=True)

    def test_resolve_from_profile(self) -> None:
        options = resolve_ablation_options(profile={"self_contract": True})
        self.assertTrue(options.self_contract)
        self.assertEqual(options.ablation_arm, "self_contract")


class SelfContractFreezeGateTests(unittest.TestCase):
    def test_freeze_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_self_contract_workspace(root)
            contracts = root / "contracts"
            (contracts / "test_basic.py").write_text(
                textwrap.dedent(
                    """\
                    def test_api_exists():
                        import featurelifted
                        assert hasattr(featurelifted, "Foo")
                    """
                ),
                encoding="utf-8",
            )
            meta = freeze_contracts(root)
            self.assertTrue((root / "contracts.lock").is_file())
            self.assertTrue((root / "CONTRACT_MANIFEST.json").is_file())
            self.assertEqual(meta["file_count"], 2)  # README + test
            check = verify_contracts_frozen(root)
            self.assertTrue(check["ok"], check)
            # Tamper then re-check without rewriting lock.
            (contracts / "test_basic.py").write_text(
                "def test_api_exists():\n    assert False\n",
                encoding="utf-8",
            )
            bad = verify_contracts_frozen(root)
            self.assertFalse(bad["ok"])
            self.assertIn("mismatch", str(bad.get("error")))

    def test_author_gate_rejects_assert_true_and_vacuous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_self_contract_workspace(root)
            contracts = root / "contracts"
            (contracts / "test_vacuous.py").write_text(
                textwrap.dedent(
                    """\
                    def test_a():
                        assert True
                    def test_b():
                        assert True
                    def test_c():
                        assert True
                    def test_d():
                        assert True
                    def test_e():
                        assert True
                    """
                ),
                encoding="utf-8",
            )

            def _fake_verify(*_a, **_k):
                return {
                    "ok": True,
                    "returncode": 0,
                    "stdout_tail": "5 passed",
                    "stderr_tail": "",
                }

            with mock.patch(
                "featureliftbench.self_contract.author_gate.verify_submission_contracts",
                side_effect=_fake_verify,
            ):
                gate = evaluate_author_gate(root, use_docker=False)
            self.assertFalse(gate["ok"])
            joined = " ".join(gate["errors"])
            self.assertIn("assert True", joined)
            self.assertIn("vacuous", joined)

    def test_author_gate_accepts_failing_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install_self_contract_workspace(root)
            contracts = root / "contracts"
            (contracts / "test_real.py").write_text(
                textwrap.dedent(
                    """\
                    def test_one():
                        from featurelifted import Foo
                        assert Foo().bar() == 1
                    def test_two():
                        from featurelifted import Foo
                        assert Foo().baz() == 2
                    def test_three():
                        from featurelifted import Foo
                        assert Foo().qux() == 3
                    def test_four():
                        from featurelifted import Foo
                        assert Foo().quux() == 4
                    def test_five():
                        from featurelifted import Foo
                        assert Foo().corge() == 5
                    """
                ),
                encoding="utf-8",
            )

            def _fake_verify(*_a, **_k):
                return {
                    "ok": False,
                    "returncode": 1,
                    "stdout_tail": "5 failed",
                    "stderr_tail": "ImportError: cannot import name Foo",
                }

            with mock.patch(
                "featureliftbench.self_contract.author_gate.verify_submission_contracts",
                side_effect=_fake_verify,
            ):
                gate = evaluate_author_gate(root, use_docker=False)
            self.assertTrue(gate["ok"], gate)
            self.assertEqual(gate["test_count"], 5)


if __name__ == "__main__":
    unittest.main()
