from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from featureliftbench.benchmark_gate import (
    FAIL,
    MEETS,
    PASS,
    ReviewerResponseError,
    UNDETERMINED,
    VIOLATES,
    GateRunOptions,
    ReviewerConfig,
    _agent_initial_prompt,
    _agent_review_check,
    _api_review_check,
    _bounded_source_excerpt,
    _hidden_nodeid_excerpt,
    _surface_check,
    _validate_review,
    aggregate_label,
    load_adjudications,
    run_benchmark_gate,
    reviewer_config_from_environment,
)
from featureliftbench.paths import REPO_ROOT


TASKS = REPO_ROOT / "benchmark" / "python200_hard_tasks"
GRAPHENE = TASKS / "graphene__schema_execute_core__001"
AIOHTTP = TASKS / "aiohttp__url_params_core__hard3_001"


class BenchmarkGateTests(unittest.TestCase):
    def test_blocking_aggregation_is_fail_closed(self) -> None:
        self.assertEqual(
            aggregate_label({"a": {"blocking": True, "status": PASS}}),
            MEETS,
        )
        self.assertEqual(
            aggregate_label({"a": {"blocking": True, "status": UNDETERMINED}}),
            UNDETERMINED,
        )
        self.assertEqual(
            aggregate_label(
                {
                    "a": {"blocking": True, "status": UNDETERMINED},
                    "b": {"blocking": True, "status": FAIL},
                }
            ),
            VIOLATES,
        )
        self.assertEqual(
            aggregate_label(
                {
                    "blocking": {"blocking": True, "status": PASS},
                    "advisory": {"blocking": False, "status": UNDETERMINED},
                }
            ),
            MEETS,
        )

    def test_graphene_scope_regression_is_clear(self) -> None:
        metadata = json.loads((GRAPHENE / "metadata.json").read_text(encoding="utf-8"))
        check, findings = _surface_check(
            GRAPHENE,
            metadata["public_spec"],
            {},
        )
        self.assertEqual(check["status"], PASS)
        self.assertEqual(findings, [])

    def test_c1_hit_is_pending_until_adjudicated(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        pending, findings = _surface_check(AIOHTTP, metadata["public_spec"], {})
        self.assertEqual(pending["status"], UNDETERMINED)
        self.assertEqual(pending["adjudication"], "pending")
        self.assertTrue(any(row.get("member") == "CIMultiDict.__setitem__" for row in findings))

        adjudications = {
            (AIOHTTP.name, "L2_C1_SURFACE"): {
                "verdict": "confirmed_violation",
                "rationale": "owner and undeclared member manually confirmed",
                "provenance": "test",
            }
        }
        confirmed, _ = _surface_check(AIOHTTP, metadata["public_spec"], adjudications)
        self.assertEqual(confirmed["status"], FAIL)
        self.assertEqual(confirmed["adjudication"], "confirmed_violation")

    def test_adjudication_csv_rejects_unknown_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "adjudications.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["task_id", "rule", "verdict"])
                writer.writeheader()
                writer.writerow({
                    "task_id": AIOHTTP.name,
                    "rule": "L2_C1_SURFACE",
                    "verdict": "probably_bad",
                })
            with self.assertRaises(ValueError):
                load_adjudications(path)

    def test_api_review_citations_accept_mechanical_surface_path(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        nodeid = metadata["evaluation_spec"]["hidden_test_mappings"][0]["nodeid"]
        behavior = metadata["evaluation_spec"]["hidden_test_mappings"][0]["behavior_ids"][0]
        review = {
            "surface_compliance": "fail",
            "hidden_fairness": "underdetermined",
            "summary": "undeclared mutation surface",
            "findings": [
                {
                    "rule": "surface",
                    "behavior_ids": [behavior],
                    "hidden_nodeids": [nodeid],
                    "api_paths": ["CIMultiDict.__setitem__"],
                    "source_paths": ["aiohttp/helpers.py"],
                    "verdict": "confirmed_violation",
                    "reason": "hidden mutation path is not declared",
                }
            ],
        }
        errors = _validate_review(
            review,
            metadata=metadata,
            source_paths={"aiohttp/helpers.py"},
            finding_api_paths={"CIMultiDict.__setitem__"},
        )
        self.assertEqual(errors, [])

    def test_api_review_accepts_featurelifted_alias_for_mechanical_member(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        nodeid = metadata["evaluation_spec"]["hidden_test_mappings"][0]["nodeid"]
        behavior = metadata["evaluation_spec"]["hidden_test_mappings"][0]["behavior_ids"][0]
        review = {
            "surface_compliance": "fail",
            "hidden_fairness": "undecided",
            "summary": "full public-package path for a mechanical member",
            "findings": [
                {
                    "rule": "surface",
                    "behavior_ids": [behavior],
                    "hidden_nodeids": [nodeid],
                    "api_paths": ["featurelifted.CIMultiDict.__setitem__"],
                    "source_paths": ["aiohttp/helpers.py"],
                    "verdict": "confirmed_violation",
                    "reason": "the hidden evaluator uses the mechanically observed member",
                }
            ],
        }
        errors = _validate_review(
            review,
            metadata=metadata,
            source_paths={"aiohttp/helpers.py"},
            finding_api_paths={"CIMultiDict.__setitem__"},
        )
        self.assertEqual(errors, [])

    def test_repair_review_uses_explicit_scope_verdict(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        nodeid = metadata["evaluation_spec"]["hidden_test_mappings"][0]["nodeid"]
        behavior = metadata["evaluation_spec"]["hidden_test_mappings"][0]["behavior_ids"][0]
        review = {
            "surface_compliance": "pass",
            "hidden_fairness": "fair",
            "repair_scope": "scope_preserved",
            "summary": "the repair discloses an existing obligation",
            "findings": [
                {
                    "rule": "repair_scope",
                    "behavior_ids": [behavior],
                    "hidden_nodeids": [nodeid],
                    "api_paths": ["featurelifted.build_url"],
                    "source_paths": ["aiohttp/helpers.py"],
                    "verdict": "scope_preserved",
                    "reason": "the old behavior already covered this operation",
                }
            ],
        }
        errors = _validate_review(
            review,
            metadata=metadata,
            source_paths={"aiohttp/helpers.py"},
            repair_context={"repair_categories": ["C1"]},
        )
        self.assertEqual(errors, [])

        review["findings"][0]["verdict"] = "fair"
        errors = _validate_review(
            review,
            metadata=metadata,
            source_paths={"aiohttp/helpers.py"},
            repair_context={"repair_categories": ["C1"]},
        )
        self.assertIn("repair_scope finding verdict does not match repair_scope", errors)

    def test_api_review_finding_stays_pending(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        nodeid = metadata["evaluation_spec"]["hidden_test_mappings"][0]["nodeid"]
        behavior = metadata["evaluation_spec"]["hidden_test_mappings"][0]["behavior_ids"][0]
        review = {
            "surface_compliance": "fail",
            "hidden_fairness": "underdetermined",
            "summary": "review requires adjudication",
            "findings": [
                {
                    "rule": "surface",
                    "behavior_ids": [behavior],
                    "hidden_nodeids": [nodeid],
                    "api_paths": ["CIMultiDict.__setitem__"],
                    "source_paths": ["aiohttp/helpers.py"],
                    "verdict": "confirmed_violation",
                    "reason": "API evidence only; not a release verdict",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            path = source / "aiohttp" / "helpers.py"
            path.parent.mkdir()
            path.write_text("def build_url():\n    return None\n", encoding="utf-8")
            reviewer = ReviewerConfig(
                model="test-model",
                api_base="http://review.invalid/v1",
                api_key="test-key",
            )
            with mock.patch(
                "featureliftbench.benchmark_gate._call_reviewer",
                return_value=(review, {"total_tokens": 42}),
            ):
                check, findings = _api_review_check(
                    task_dir=AIOHTTP,
                    metadata=metadata,
                    source_root=source,
                    snapshot=None,
                    findings=[{"member": "CIMultiDict.__setitem__"}],
                    config=reviewer,
                )
        self.assertEqual(check["status"], UNDETERMINED)
        self.assertEqual(check["adjudication"], "pending")
        self.assertEqual(check["details"]["usage"]["total_tokens"], 42)
        self.assertEqual(findings[0]["rule"], "L2_API_REVIEW")
        self.assertEqual(findings[0]["semantic_rule"], "surface")

    def test_large_source_is_reduced_to_symbol_focused_excerpt(self) -> None:
        text = "\n".join(
            ["padding = 1"] * 500
            + ["class Widget:", "    def run(self):", "        return 1"]
            + ["padding = 2"] * 500
        )
        excerpt = _bounded_source_excerpt(text, leaves={"Widget"}, limit=4_000)
        self.assertLessEqual(len(excerpt), 4_000)
        self.assertIn("class Widget:", excerpt)
        self.assertIn("canonical source excerpt", excerpt)

    def test_reviewer_config_can_read_safe_dotenv_values(self) -> None:
        config = reviewer_config_from_environment(
            model="deepseek-v4-flash",
            api_base=None,
            api_key_env="FEATURELIFTBENCH_VALIDATOR_API_KEY",
            timeout_seconds=30,
            env_values={
                "FEATURELIFTBENCH_API_BASE": "https://review.example/v1",
                "FEATURELIFTBENCH_API_KEY": "secret",
            },
        )
        self.assertEqual(config.api_base, "https://review.example/v1")
        self.assertEqual(config.api_key, "secret")

    def test_hidden_nodeid_tool_returns_only_requested_test(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        mappings = metadata["evaluation_spec"]["hidden_test_mappings"]
        requested = mappings[0]["nodeid"]
        other_name = mappings[1]["nodeid"].split("::")[-1]
        result = _hidden_nodeid_excerpt(AIOHTTP, requested, 8_000)
        self.assertNotIn("error", result)
        self.assertIn(requested.split("::")[-1], result["excerpt"])
        self.assertNotIn(other_name, result["excerpt"])

    def test_constrained_agent_inspects_then_submits_cited_review(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        mappings = metadata["evaluation_spec"]["hidden_test_mappings"]
        nodeids = [row["nodeid"] for row in mappings]
        behavior = mappings[0]["behavior_ids"][0]
        actions = [
            ({"action": "inspect_hidden", "nodeids": nodeids}, {"total_tokens": 100}),
            (
                {"action": "inspect_source", "symbols": ["aiohttp.helpers.build_url"]},
                {"total_tokens": 100},
            ),
            ReviewerResponseError(
                "reviewer response contains no JSON object",
                usage={"total_tokens": 50},
                finish_reason="length",
                content_chars=0,
                reasoning_chars=2_000,
            ),
            (
                {
                    "action": "submit",
                    "review": {
                        "surface_compliance": "pass",
                        "hidden_fairness": "fair",
                        "summary": "all mapped observations are grounded",
                        "findings": [
                            {
                                "rule": "fairness",
                                "behavior_ids": [behavior],
                                "hidden_nodeids": [nodeids[0]],
                                "api_paths": ["featurelifted.build_url"],
                                "source_paths": ["aiohttp.helpers.build_url"],
                                "verdict": "fair",
                                "reason": "the inspected behavior matches the declared clause",
                            }
                        ],
                    },
                },
                {"total_tokens": 100},
            ),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            path = source / "aiohttp" / "helpers.py"
            path.parent.mkdir()
            path.write_text("def build_url(value):\n    return value\n", encoding="utf-8")
            snapshot = mock.Mock()
            snapshot.modules = {"aiohttp.helpers": path}
            snapshot.longest_module_prefix.return_value = (
                "aiohttp.helpers",
                "build_url",
            )
            reviewer = ReviewerConfig(
                model="test-model",
                api_base="http://review.invalid/v1",
                api_key="test-key",
                mode="agent",
                agent_pending_only=False,
            )
            with mock.patch(
                "featureliftbench.benchmark_gate._call_chat",
                side_effect=actions,
            ):
                check, findings = _agent_review_check(
                    task_dir=AIOHTTP,
                    metadata=metadata,
                    source_root=source,
                    snapshot=snapshot,
                    findings=[],
                    config=reviewer,
                )
        self.assertEqual(check["status"], PASS)
        self.assertEqual(check["details"]["turns"], 4)
        self.assertEqual(check["details"]["usage"]["total_tokens"], 350)
        self.assertEqual(check["details"]["trace"][2]["action"], "invalid_response")
        submit_trace = check["details"]["trace"][3]
        self.assertEqual(
            submit_trace["citation_normalizations"],
            [
                {
                    "submitted": "aiohttp.helpers.build_url",
                    "canonical_path": "aiohttp/helpers.py",
                }
            ],
        )
        self.assertEqual(
            check["details"]["review"]["findings"][0]["source_paths"],
            ["aiohttp/helpers.py"],
        )
        self.assertEqual(findings[0]["rule"], "L2_AGENT_REVIEW")

    def test_invalid_source_request_gets_one_protocol_repair_turn(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        nodeids = [
            row["nodeid"]
            for row in metadata["evaluation_spec"]["hidden_test_mappings"]
        ]
        behavior = metadata["evaluation_spec"]["hidden_test_mappings"][0]["behavior_ids"][0]
        allowed_symbol = metadata["public_spec"]["source_entrypoints"][0]
        actions = [
            ({"action": "inspect_source", "symbols": ["not.an.allowed.symbol"]}, {"total_tokens": 10}),
            ({"action": "inspect_source", "symbols": [allowed_symbol]}, {"total_tokens": 20}),
            ({"action": "inspect_hidden", "nodeids": nodeids}, {"total_tokens": 30}),
            (
                {
                    "action": "submit",
                    "review": {
                        "surface_compliance": "pass",
                        "hidden_fairness": "fair",
                        "summary": "recovered from an invalid evidence request",
                        "findings": [
                            {
                                "rule": "fairness",
                                "behavior_ids": [behavior],
                                "hidden_nodeids": [nodeids[0]],
                                "api_paths": ["featurelifted.build_url"],
                                "source_paths": ["aiohttp/helpers.py"],
                                "verdict": "fair",
                                "reason": "the inspected behavior matches the public clause",
                            }
                        ],
                    },
                },
                {"total_tokens": 40},
            ),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            path = source / "aiohttp" / "helpers.py"
            path.parent.mkdir()
            path.write_text("def strip_auth_from_url(value):\n    return value\n", encoding="utf-8")
            snapshot = mock.Mock()
            snapshot.modules = {"aiohttp.helpers": path}
            snapshot.longest_module_prefix.return_value = (
                "aiohttp.helpers",
                "strip_auth_from_url",
            )
            reviewer = ReviewerConfig(
                model="test-model",
                api_base="http://review.invalid/v1",
                api_key="test-key",
                mode="agent",
                agent_pending_only=False,
                agent_max_turns=4,
            )
            with mock.patch(
                "featureliftbench.benchmark_gate._call_chat",
                side_effect=actions,
            ):
                check, _findings = _agent_review_check(
                    task_dir=AIOHTTP,
                    metadata=metadata,
                    source_root=source,
                    snapshot=snapshot,
                    findings=[],
                    config=reviewer,
                )
        self.assertEqual(check["status"], PASS)
        self.assertEqual(check["details"]["turns"], 4)
        self.assertTrue(check["details"]["trace"][0]["rejected"])
        self.assertEqual(check["details"]["usage"]["total_tokens"], 100)

    def test_surface_flag_accepts_mechanical_member_without_all_nodeids(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        nodeid = metadata["evaluation_spec"]["hidden_test_mappings"][0]["nodeid"]
        behavior = metadata["evaluation_spec"]["hidden_test_mappings"][0]["behavior_ids"][0]
        actions = [
            ({"action": "inspect_hidden", "nodeids": [nodeid]}, {"total_tokens": 40}),
            (
                {
                    "action": "submit",
                    "review": {
                        "surface_compliance": "fail",
                        "hidden_fairness": "undecided",
                        "summary": "undeclared subscript surface",
                        "findings": [
                            {
                                "rule": "surface",
                                "behavior_ids": [behavior],
                                "hidden_nodeids": [nodeid],
                                "api_paths": ["featurelifted.CIMultiDict.__setitem__"],
                                "source_paths": [],
                                "verdict": "confirmed_violation",
                                "reason": "hidden uses undeclared __setitem__",
                            }
                        ],
                    },
                },
                {"total_tokens": 80},
            ),
        ]
        reviewer = ReviewerConfig(
            model="test-model",
            api_base="http://review.invalid/v1",
            api_key="test-key",
            mode="agent",
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            with mock.patch(
                "featureliftbench.benchmark_gate._call_chat",
                side_effect=actions,
            ):
                check, findings = _agent_review_check(
                    task_dir=AIOHTTP,
                    metadata=metadata,
                    source_root=source,
                    snapshot=None,
                    findings=[{"member": "CIMultiDict.__setitem__"}],
                    config=reviewer,
                )
        self.assertEqual(check["status"], UNDETERMINED)
        self.assertEqual(check["reason"], "validator agent flagged package defects")
        self.assertEqual(findings[0]["verdict"], "confirmed_violation")
        self.assertEqual(
            findings[0]["api_paths"],
            ["featurelifted.CIMultiDict.__setitem__"],
        )

    def test_rejected_submit_gets_one_citation_repair_turn(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        nodeid = metadata["evaluation_spec"]["hidden_test_mappings"][0]["nodeid"]
        behavior = metadata["evaluation_spec"]["hidden_test_mappings"][0]["behavior_ids"][0]
        actions = [
            ({"action": "inspect_hidden", "nodeids": [nodeid]}, {"total_tokens": 40}),
            (
                {
                    "action": "submit",
                    "review": {
                        "surface_compliance": "fail",
                        "hidden_fairness": "undecided",
                        "summary": "bad citations",
                        "findings": [
                            {
                                "rule": "surface",
                                "behavior_ids": [behavior],
                                "hidden_nodeids": [nodeid],
                                "api_paths": ["NotARealType.__setitem__"],
                                "source_paths": [],
                                "verdict": "confirmed_violation",
                                "reason": "undeclared member",
                            }
                        ],
                    },
                },
                {"total_tokens": 50},
            ),
            (
                {
                    "action": "submit",
                    "review": {
                        "surface_compliance": "fail",
                        "hidden_fairness": "undecided",
                        "summary": "repaired citations",
                        "findings": [
                            {
                                "rule": "surface",
                                "behavior_ids": [behavior],
                                "hidden_nodeids": [nodeid],
                                "api_paths": ["CIMultiDict.__setitem__"],
                                "source_paths": [],
                                "verdict": "confirmed_violation",
                                "reason": "undeclared member after repair",
                            }
                        ],
                    },
                },
                {"total_tokens": 50},
            ),
        ]
        reviewer = ReviewerConfig(
            model="test-model",
            api_base="http://review.invalid/v1",
            api_key="test-key",
            mode="agent",
            agent_max_turns=2,
        )
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch(
                "featureliftbench.benchmark_gate._call_chat",
                side_effect=actions,
            ):
                check, findings = _agent_review_check(
                    task_dir=AIOHTTP,
                    metadata=metadata,
                    source_root=Path(temporary),
                    snapshot=None,
                    findings=[{"member": "CIMultiDict.__setitem__"}],
                    config=reviewer,
                )
        self.assertEqual(check["details"]["turns"], 3)
        self.assertTrue(check["details"]["trace"][1]["rejected"])
        self.assertEqual(findings[0]["api_paths"], ["CIMultiDict.__setitem__"])
        self.assertEqual(check["reason"], "validator agent flagged package defects")

    def test_source_symbol_citation_normalizes_to_inspected_file(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        mappings = metadata["evaluation_spec"]["hidden_test_mappings"]
        nodeids = [row["nodeid"] for row in mappings]
        behavior = mappings[0]["behavior_ids"][0]
        actions = [
            ({"action": "inspect_hidden", "nodeids": nodeids}, {"total_tokens": 40}),
            (
                {"action": "inspect_source", "symbols": ["aiohttp.helpers.build_url"]},
                {"total_tokens": 40},
            ),
            (
                {
                    "action": "submit",
                    "review": {
                        "surface_compliance": "pass",
                        "hidden_fairness": "fair",
                        "summary": "symbol citation should normalize",
                        "findings": [
                            {
                                "rule": "fairness",
                                "behavior_ids": [behavior],
                                "hidden_nodeids": [nodeids[0]],
                                "api_paths": ["featurelifted.build_url"],
                                "source_paths": ["aiohttp.helpers.build_url"],
                                "verdict": "fair",
                                "reason": "normalized from symbol to file path",
                            }
                        ],
                    },
                },
                {"total_tokens": 40},
            ),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            path = source / "aiohttp" / "helpers.py"
            path.parent.mkdir()
            path.write_text("def build_url(value):\n    return value\n", encoding="utf-8")
            snapshot = mock.Mock()
            snapshot.modules = {"aiohttp.helpers": path}
            snapshot.longest_module_prefix.return_value = ("aiohttp.helpers", "build_url")
            reviewer = ReviewerConfig(
                model="test-model",
                api_base="http://review.invalid/v1",
                api_key="test-key",
                mode="agent",
                agent_pending_only=False,
            )
            with mock.patch(
                "featureliftbench.benchmark_gate._call_chat",
                side_effect=actions,
            ):
                check, _findings = _agent_review_check(
                    task_dir=AIOHTTP,
                    metadata=metadata,
                    source_root=source,
                    snapshot=snapshot,
                    findings=[],
                    config=reviewer,
                )
        self.assertEqual(check["status"], PASS)
        self.assertEqual(
            check["details"]["review"]["findings"][0]["source_paths"],
            ["aiohttp/helpers.py"],
        )

    def test_prompt_treats_canonical_source_as_the_implementation(self) -> None:
        metadata = json.loads((GRAPHENE / "metadata.json").read_text(encoding="utf-8"))
        prompt = _agent_initial_prompt(
            task_id=GRAPHENE.name,
            metadata=metadata,
            findings=[],
            config=ReviewerConfig(
                model="test-model",
                api_base="http://review.invalid/v1",
                api_key="test-key",
            ),
        )
        self.assertIn("no separate featurelifted/", prompt)
        self.assertIn('"mechanical_surface_status": "clear"', prompt)

    def test_clear_surface_cannot_stay_undetermined_after_hidden_inspect(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        mappings = metadata["evaluation_spec"]["hidden_test_mappings"]
        nodeids = [row["nodeid"] for row in mappings]
        behavior = mappings[0]["behavior_ids"][0]
        fair_review = {
            "surface_compliance": "pass",
            "hidden_fairness": "fair",
            "summary": "canonical source is enough",
            "findings": [
                {
                    "rule": "fairness",
                    "behavior_ids": [behavior],
                    "hidden_nodeids": [nodeids[0]],
                    "api_paths": ["featurelifted.build_url"],
                    "source_paths": ["aiohttp/helpers.py"],
                    "verdict": "fair",
                    "reason": "hidden matches the public clause",
                }
            ],
        }
        actions = [
            ({"action": "inspect_hidden", "nodeids": nodeids}, {"total_tokens": 40}),
            (
                {"action": "inspect_source", "symbols": ["aiohttp.helpers.build_url"]},
                {"total_tokens": 40},
            ),
            (
                {
                    "action": "submit",
                    "review": {
                        **fair_review,
                        "surface_compliance": "undetermined",
                        "summary": "waiting for featurelifted tree",
                    },
                },
                {"total_tokens": 40},
            ),
            ({"action": "submit", "review": fair_review}, {"total_tokens": 40}),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            path = source / "aiohttp" / "helpers.py"
            path.parent.mkdir()
            path.write_text("def build_url(value):\n    return value\n", encoding="utf-8")
            snapshot = mock.Mock()
            snapshot.modules = {"aiohttp.helpers": path}
            snapshot.longest_module_prefix.return_value = ("aiohttp.helpers", "build_url")
            reviewer = ReviewerConfig(
                model="test-model",
                api_base="http://review.invalid/v1",
                api_key="test-key",
                mode="agent",
                agent_pending_only=False,
            )
            with mock.patch(
                "featureliftbench.benchmark_gate._call_chat",
                side_effect=actions,
            ):
                check, _findings = _agent_review_check(
                    task_dir=AIOHTTP,
                    metadata=metadata,
                    source_root=source,
                    snapshot=snapshot,
                    findings=[],
                    config=reviewer,
                )
        self.assertTrue(check["details"]["trace"][2]["rejected"])
        self.assertIn("featurelifted tree", " ".join(check["details"]["trace"][2]["rejected"]))
        self.assertEqual(check["status"], PASS)

    def test_clear_surface_cannot_fail_on_featurelifted_rename(self) -> None:
        metadata = json.loads((AIOHTTP / "metadata.json").read_text(encoding="utf-8"))
        mappings = metadata["evaluation_spec"]["hidden_test_mappings"]
        nodeids = [row["nodeid"] for row in mappings]
        behavior = mappings[0]["behavior_ids"][0]
        pass_review = {
            "surface_compliance": "pass",
            "hidden_fairness": "fair",
            "summary": "rename is not a defect",
            "findings": [
                {
                    "rule": "fairness",
                    "behavior_ids": [behavior],
                    "hidden_nodeids": [nodeids[0]],
                    "api_paths": ["featurelifted.build_url"],
                    "source_paths": ["aiohttp/helpers.py"],
                    "verdict": "fair",
                    "reason": "canonical source matches the clause",
                }
            ],
        }
        actions = [
            ({"action": "inspect_hidden", "nodeids": nodeids}, {"total_tokens": 40}),
            (
                {"action": "inspect_source", "symbols": ["aiohttp.helpers.build_url"]},
                {"total_tokens": 40},
            ),
            (
                {
                    "action": "submit",
                    "review": {
                        "surface_compliance": "fail",
                        "hidden_fairness": "fair",
                        "summary": "source is graphene-named",
                        "findings": [
                            {
                                "rule": "surface",
                                "behavior_ids": [behavior],
                                "hidden_nodeids": [nodeids[0]],
                                "api_paths": ["featurelifted.build_url"],
                                "source_paths": ["aiohttp/helpers.py"],
                                "verdict": "confirmed_violation",
                                "reason": "canonical source is not named featurelifted",
                            }
                        ],
                    },
                },
                {"total_tokens": 40},
            ),
            ({"action": "submit", "review": pass_review}, {"total_tokens": 40}),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            path = source / "aiohttp" / "helpers.py"
            path.parent.mkdir()
            path.write_text("def build_url(value):\n    return value\n", encoding="utf-8")
            snapshot = mock.Mock()
            snapshot.modules = {"aiohttp.helpers": path}
            snapshot.longest_module_prefix.return_value = ("aiohttp.helpers", "build_url")
            reviewer = ReviewerConfig(
                model="test-model",
                api_base="http://review.invalid/v1",
                api_key="test-key",
                mode="agent",
                agent_pending_only=False,
            )
            with mock.patch(
                "featureliftbench.benchmark_gate._call_chat",
                side_effect=actions,
            ):
                check, findings = _agent_review_check(
                    task_dir=AIOHTTP,
                    metadata=metadata,
                    source_root=source,
                    snapshot=snapshot,
                    findings=[],
                    config=reviewer,
                )
        self.assertTrue(check["details"]["trace"][2]["rejected"])
        self.assertIn("extraction alias", " ".join(check["details"]["trace"][2]["rejected"]))
        self.assertEqual(check["status"], PASS)
        self.assertFalse(any(item.get("verdict") == "confirmed_violation" for item in findings))

    def test_smoke_run_is_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "gate"
            payload = run_benchmark_gate(
                GateRunOptions(
                    benchmark="python200_hard",
                    output=output,
                    task_ids=(GRAPHENE.name,),
                    source_materialization=False,
                )
            )
            self.assertEqual(payload["task_count"], 1)
            self.assertFalse(payload["publication"]["selection_written"])
            self.assertTrue((output / "gate_report.json").is_file())
            self.assertTrue((output / "undetermined.txt").is_file())

    def test_api_review_requires_private_data_policy_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            reviewer = ReviewerConfig(
                model="test-model",
                api_base="http://127.0.0.1:9/v1",
                api_key="not-a-real-key",
            )
            with self.assertRaisesRegex(ValueError, "no-training/no-retention"):
                run_benchmark_gate(
                    GateRunOptions(
                        benchmark="python200_hard",
                        output=Path(temporary) / "gate",
                        task_ids=(GRAPHENE.name,),
                        source_materialization=False,
                        reviewer=reviewer,
                    )
                )

    def test_agent_default_escalates_only_mechanically_ambiguous_tasks(self) -> None:
        reviewer = ReviewerConfig(
            model="test-model",
            api_base="http://review.invalid/v1",
            api_key="test-key",
            mode="agent",
            agent_pending_only=True,
        )
        agent_result = (
            {
                "status": PASS,
                "blocking": False,
                "reason": "mock agent review",
                "mechanical_result": "clear",
                "adjudication": "not_needed",
            },
            [],
        )
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch(
                "featureliftbench.benchmark_gate._agent_review_check",
                return_value=agent_result,
            ) as review:
                payload = run_benchmark_gate(
                    GateRunOptions(
                        benchmark="python200_hard",
                        output=Path(temporary) / "gate",
                        task_ids=(GRAPHENE.name, AIOHTTP.name),
                        reviewer=reviewer,
                        private_evaluator_policy_acknowledged=True,
                    )
                )
        self.assertEqual(review.call_count, 1)
        rows = {row["task_id"]: row for row in payload["tasks"]}
        graphene = rows[GRAPHENE.name]["checks"]["L2_AGENT_REVIEW"]
        self.assertTrue(graphene["details"]["skipped"])


if __name__ == "__main__":
    unittest.main()
