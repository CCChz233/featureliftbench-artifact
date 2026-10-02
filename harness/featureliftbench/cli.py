"""Command line interface for FeatureLiftBench."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .agent_adapters import SUPPORTED_AGENTS
from .catalog import add_catalog_parser
from .catalog import dispatch_catalog
from .agent_docker import DEFAULT_AGENT_IMAGE
from .docker_eval import DEFAULT_EVAL_IMAGE
from .docker_eval import DEFAULT_GO_EVAL_IMAGE
from .docker_eval import evaluate_submission_docker
from .evaluator import evaluate_submission
from .paths import DEFAULT_AGENT_CONFIG
from .paths import DEFAULT_LOCAL_CONFIG
from .paths import resolve_task_input
from .task_render import render_agent_workspace_task, render_public_task
from .task_spec_migrate import annotate_legacy_status, migrate_task_to_compliant
from .validate import validate_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="featureliftbench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate-task", help="validate a task directory")
    validate_parser.add_argument("task_dir", type=Path)
    validate_parser.add_argument("--json", action="store_true", help="print machine-readable output")

    benchmark_gate_parser = subparsers.add_parser(
        "validate-benchmark",
        help="run the read-only, evidence-backed validation gate for a named suite",
    )
    benchmark_gate_parser.add_argument(
        "--benchmark",
        default="python200_hard",
        help="named suite from benchmark/suites.toml",
    )
    benchmark_gate_parser.add_argument(
        "--output",
        type=Path,
        help="new report directory; defaults to reports/benchmark_gate/<suite>_<time>",
    )
    benchmark_gate_parser.add_argument(
        "--task-id",
        action="append",
        default=[],
        help="limit to one task id; repeat for a smoke subset",
    )
    benchmark_gate_parser.add_argument(
        "--no-source-materialization",
        action="store_true",
        help="verify archive identity but leave source-dependent checks undetermined",
    )
    benchmark_gate_parser.add_argument(
        "--oracle-summary",
        type=Path,
        help="N=3 oracle revalidation summary; defaults to the Python-200' audit",
    )
    benchmark_gate_parser.add_argument(
        "--upstream-direct-summary",
        type=Path,
        help="G2' upstream-direct submission audit; defaults to the Python-200' audit",
    )
    benchmark_gate_parser.add_argument(
        "--adjudications",
        type=Path,
        help="CSV that confirms, overturns, or leaves mechanical findings unresolved",
    )
    benchmark_gate_parser.add_argument(
        "--api-review",
        action="store_true",
        help="use the legacy one-shot reviewer on explicitly approved private evidence",
    )
    benchmark_gate_parser.add_argument(
        "--agent-review",
        action="store_true",
        help="use the constrained multi-turn validator agent on ambiguous tasks",
    )
    benchmark_gate_parser.add_argument("--review-model")
    benchmark_gate_parser.add_argument("--review-api-base")
    benchmark_gate_parser.add_argument(
        "--review-api-key-env",
        default="FEATURELIFTBENCH_VALIDATOR_API_KEY",
    )
    benchmark_gate_parser.add_argument(
        "--review-env-file",
        type=Path,
        help="dotenv-style reviewer configuration; secrets are never written to reports",
    )
    benchmark_gate_parser.add_argument(
        "--review-timeout-seconds",
        type=int,
        default=180,
    )
    benchmark_gate_parser.add_argument(
        "--review-max-output-tokens",
        type=int,
        default=4096,
    )
    benchmark_gate_parser.add_argument(
        "--review-reasoning-effort",
        choices=("low", "high", "max"),
        default="low",
    )
    benchmark_gate_parser.add_argument(
        "--agent-max-turns",
        type=int,
        default=6,
    )
    benchmark_gate_parser.add_argument(
        "--agent-max-total-tokens",
        type=int,
        default=40000,
    )
    benchmark_gate_parser.add_argument(
        "--agent-review-all-selected",
        action="store_true",
        help="also run the agent on mechanically clear selected controls",
    )
    benchmark_gate_parser.add_argument(
        "--acknowledge-private-evaluator-policy",
        action="store_true",
        help="confirm the endpoint is authorized for no-training/no-retention evaluator data",
    )
    benchmark_gate_parser.add_argument(
        "--require-pass",
        action="store_true",
        help="return non-zero unless every selected task meets all blocking checks",
    )

    render_parser = subparsers.add_parser(
        "render-task",
        help="render TASK.md from metadata.public_spec",
    )
    render_parser.add_argument("task_dir", type=Path)
    render_parser.add_argument(
        "--write",
        action="store_true",
        help="write rendered TASK.md into the task directory",
    )

    migrate_parser = subparsers.add_parser(
        "migrate-task-spec",
        help="migrate a legacy pilot task to constitution-compliant public_spec",
    )
    migrate_parser.add_argument("task_dir", type=Path)
    migrate_parser.add_argument("--dry-run", action="store_true")
    migrate_parser.add_argument("--json", action="store_true")

    annotate_parser = subparsers.add_parser(
        "annotate-spec-status",
        help="mark tasks without public_spec as spec_status=legacy",
    )
    annotate_parser.add_argument("tasks_root", type=Path)
    annotate_parser.add_argument("--dry-run", action="store_true")

    eval_parser = subparsers.add_parser("eval", help="evaluate a submission")
    eval_parser.add_argument("task_dir", type=Path)
    eval_parser.add_argument("submission_dir", type=Path)
    eval_parser.add_argument("--output", type=Path, required=True)
    eval_parser.add_argument(
        "--functional-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    eval_parser.add_argument(
        "--trusted-evaluation-capsule",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    eval_parser.add_argument(
        "--docker",
        action="store_true",
        help="run evaluation inside the featureliftbench-eval Docker image",
    )
    eval_parser.add_argument(
        "--docker-image",
        default=DEFAULT_EVAL_IMAGE,
        help=(
            f"Docker image for --docker "
            f"(default: {DEFAULT_EVAL_IMAGE}; Go tasks auto-use {DEFAULT_GO_EVAL_IMAGE})"
        ),
    )

    score_parser = subparsers.add_parser("score", help="print scores from a result file")
    score_parser.add_argument("result_json", type=Path)

    run_agent_parser = subparsers.add_parser(
        "run-agent",
        help="run an agent on one task directory or every task under a dataset root",
    )
    run_agent_parser.add_argument("input_path", type=Path)
    run_agent_parser.add_argument("--output", type=Path, required=True)
    run_agent_parser.add_argument(
        "--agent",
        default="mini-swe-agent",
        help=f"agent adapter to use; supported: {', '.join(SUPPORTED_AGENTS)}",
    )
    run_agent_parser.add_argument("--agent-bin", help="agent executable; defaults to adapter default")
    run_agent_parser.add_argument("--model", help="model name passed to the agent")
    run_agent_parser.add_argument("--config", help="agent config file path")
    run_agent_parser.add_argument(
        "--agent-config",
        type=Path,
        default=DEFAULT_AGENT_CONFIG,
        help="FeatureLiftBench agent TOML config file with profiles and model settings",
    )
    run_agent_parser.add_argument(
        "--agent-profile",
        help="profile name in --agent-config; defaults to config profile or 'default'",
    )
    test_visibility = run_agent_parser.add_mutually_exclusive_group()
    test_visibility.add_argument(
        "--agent-public-tests",
        dest="mount_public_tests",
        action="store_true",
        help="public-feedback ablation: mount benchmark public_tests/ for agent self-testing",
    )
    test_visibility.add_argument(
        "--no-agent-public-tests",
        dest="mount_public_tests",
        action="store_false",
        help="deprecated compatibility flag; evaluator tests are hidden by default",
    )
    run_agent_parser.set_defaults(mount_public_tests=None)
    source_hint_visibility = run_agent_parser.add_mutually_exclusive_group()
    source_hint_visibility.add_argument(
        "--agent-source-hints",
        dest="expose_source_hints",
        action="store_true",
        help="Entrypoint-Hint ablation: expose frozen source entrypoints to the agent",
    )
    source_hint_visibility.add_argument(
        "--no-agent-source-hints",
        dest="expose_source_hints",
        action="store_false",
        help="No-Hint Main (default): remove source entrypoints from the agent workspace",
    )
    run_agent_parser.set_defaults(expose_source_hints=None)
    run_agent_parser.add_argument(
        "--prompt-style",
        choices=("standard", "short"),
        help="standard keeps How-to/Closure Discipline; short keeps the functional contract only",
    )
    run_agent_parser.add_argument(
        "--source-context",
        choices=("full_repository", "pruned_context", "contract_only"),
        help=(
            "source workspace arm; Official Main is full_repository; "
            "contract_only is the supplementary no-source arm and does not "
            "change Main"
        ),
    )
    td_cognition = run_agent_parser.add_mutually_exclusive_group()
    td_cognition.add_argument(
        "--td-cognition",
        dest="td_cognition",
        action="store_true",
        help="TD-Cognition method arm: hard-gate submission/ until cognition scaffold + probes unlock",
    )
    td_cognition.add_argument(
        "--no-td-cognition",
        dest="td_cognition",
        action="store_false",
        help="Disable TD-Cognition hard gate (default)",
    )
    run_agent_parser.set_defaults(td_cognition=None)
    exec_contract = run_agent_parser.add_mutually_exclusive_group()
    exec_contract.add_argument(
        "--exec-contract",
        dest="exec_contract",
        action="store_true",
        help="Execution-Guided Contract arm: upstream runtime facts -> contracts -> verify",
    )
    exec_contract.add_argument(
        "--no-exec-contract",
        dest="exec_contract",
        action="store_false",
        help="Disable Execution-Guided Contract arm (default)",
    )
    run_agent_parser.set_defaults(exec_contract=None)
    run_agent_parser.add_argument(
        "--exec-contract-variant",
        choices=("clean3", "cgcc_lite", "cgcc_roc", "cgcc_rmc", "fcec"),
        help=(
            "exec-contract synthesis variant: clean3 is the best frozen template "
            "baseline; cgcc_lite adds eval-blind contrastive closure contracts; "
            "cgcc_roc adds representation/observation closure; cgcc_rmc adds "
            "required-method behavioral witnesses; fcec requires clause-bound "
            "dynamic evidence or falls back to Main"
        ),
    )
    self_contract = run_agent_parser.add_mutually_exclusive_group()
    self_contract.add_argument(
        "--self-contract",
        dest="self_contract",
        action="store_true",
        help="Self-Authored Contract arm: model writes contracts -> freeze -> implement",
    )
    self_contract.add_argument(
        "--no-self-contract",
        dest="self_contract",
        action="store_false",
        help="Disable Self-Authored Contract arm (default)",
    )
    run_agent_parser.set_defaults(self_contract=None)
    test_first_lift = run_agent_parser.add_mutually_exclusive_group()
    test_first_lift.add_argument(
        "--test-first-lift",
        dest="test_first_lift",
        action="store_true",
        help=(
            "Test-First Lift method arm: agent writes characterization cases, "
            "harness freezes upstream oracle, then agent implements"
        ),
    )
    test_first_lift.add_argument(
        "--no-test-first-lift",
        dest="test_first_lift",
        action="store_false",
        help="Disable Test-First Lift arm (default)",
    )
    run_agent_parser.set_defaults(test_first_lift=None)
    contract_closure_gate = run_agent_parser.add_mutually_exclusive_group()
    contract_closure_gate.add_argument(
        "--contract-closure-gate",
        dest="contract_closure_gate",
        action="store_true",
        help=(
            "Public Contract Closure Gate arm: check public API and agent-authored "
            "behavior evidence, then allow one bounded repair"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-contract-closure-gate",
        dest="contract_closure_gate",
        action="store_false",
        help="Disable Public Contract Closure Gate arm (default)",
    )
    contract_closure_gate.add_argument(
        "--contract-closure-gate-lite",
        dest="contract_closure_gate_lite",
        action="store_true",
        help=(
            "Low-token Public Contract Closure Gate arm: check deterministic public "
            "API structure only, then allow one separately budgeted repair"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-contract-closure-gate-lite",
        dest="contract_closure_gate_lite",
        action="store_false",
        help="Disable the low-token Public Contract Closure Gate arm (default)",
    )
    contract_closure_gate.add_argument(
        "--contract-closure-gate-lite-v1-frozen",
        dest="contract_closure_gate_lite_v1",
        action="store_true",
        help=(
            "Frozen Lite V1 arm used by the 12-task pilot: deterministic public "
            "API structure checks, no behavior cases, and the original repair budget"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-contract-closure-gate-lite-v1-frozen",
        dest="contract_closure_gate_lite_v1",
        action="store_false",
        help="Disable the frozen Lite V1 Contract Closure Gate arm (default)",
    )
    contract_closure_gate.add_argument(
        "--contract-closure-gate-lite-rescue",
        dest="contract_closure_gate_lite_rescue",
        action="store_true",
        help=(
            "Lite Rescue arm: the short V1 implementation prompt with checker v5 "
            "and selective bounded local repair"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-contract-closure-gate-lite-rescue",
        dest="contract_closure_gate_lite_rescue",
        action="store_false",
        help="Disable the Lite Rescue Contract Closure Gate arm (default)",
    )
    contract_closure_gate.add_argument(
        "--contract-closure-gate-lite-rescue-plus",
        dest="contract_closure_gate_lite_rescue_plus",
        action="store_true",
        help=(
            "Lite Rescue+ arm: selective structural repair plus one or two "
            "public behavior smoke cases under a shared 60-second budget"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-contract-closure-gate-lite-rescue-plus",
        dest="contract_closure_gate_lite_rescue_plus",
        action="store_false",
        help="Disable the Lite Rescue+ Contract Closure Gate arm (default)",
    )
    contract_closure_gate.add_argument(
        "--contract-closure-gate-v3",
        dest="contract_closure_gate_v3",
        action="store_true",
        help=(
            "V3 Public Contract Closure Gate arm: check deterministic structure and "
            "a bounded set of public behavior smoke cases, then allow one short repair"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-contract-closure-gate-v3",
        dest="contract_closure_gate_v3",
        action="store_false",
        help="Disable the V3 behavior-smoke Contract Closure Gate arm (default)",
    )
    contract_closure_gate.add_argument(
        "--contract-closure-budget-control",
        dest="contract_closure_budget_control",
        action="store_true",
        help=(
            "Equal-budget control for the Lite Gate: same primary limits and a "
            "generic review prompt, but no contract checker or gate feedback"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-contract-closure-budget-control",
        dest="contract_closure_budget_control",
        action="store_false",
        help="Disable the equal-budget Contract Closure control arm (default)",
    )
    contract_closure_gate.add_argument(
        "--adaptive-budget-v2",
        dest="adaptive_budget_v2",
        action="store_true",
        help=(
            "V2 Adaptive Budget: Main prompt with a 1.5M primary token cap, "
            "one progress checkpoint, and an optional 500K targeted-repair phase"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-adaptive-budget-v2",
        dest="adaptive_budget_v2",
        action="store_false",
        help="Disable the V2 Adaptive Budget arm (default)",
    )
    contract_closure_gate.add_argument(
        "--pre-submit-contract-audit",
        dest="pre_submit_contract_audit",
        action="store_true",
        help=(
            "Prompt-only explicit-contract audit: checklist the public Bxxx clauses "
            "before finishing; no checker, Hidden, or evaluator-test hunting"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-pre-submit-contract-audit",
        dest="pre_submit_contract_audit",
        action="store_false",
        help="Disable the pre-submit explicit-contract audit arm (default)",
    )
    contract_closure_gate.add_argument(
        "--spec-adversarial-self-test",
        dest="spec_adversarial_self_test",
        action="store_true",
        help=(
            "Spec-grounded adversarial self-test: harness matrix + filled scenarios; "
            "no Hidden, no public_tests mount, no self-reflection checklist"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-spec-adversarial-self-test",
        dest="spec_adversarial_self_test",
        action="store_false",
        help="Disable the spec-adversarial self-test arm (default)",
    )
    contract_closure_gate.add_argument(
        "--obligation-guided",
        dest="obligation_guided",
        action="store_true",
        help=(
            "Obligation-Guided Feature Lifting: frozen public-contract ledger "
            "with repo and implementation evidence; no tests, no finish intercept"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-obligation-guided",
        dest="obligation_guided",
        action="store_false",
        help="Disable Obligation-Guided Feature Lifting (default)",
    )
    contract_closure_gate.add_argument(
        "--cgvl",
        dest="cgvl",
        action="store_true",
        help=(
            "Contract-Guided Verification Loop v2: compact behavior cells, exact "
            "public-entry calls, executable assertions, isolation, and a hard finish gate"
        ),
    )
    contract_closure_gate.add_argument(
        "--no-cgvl",
        dest="cgvl",
        action="store_false",
        help="Disable CGVL (default)",
    )
    run_agent_parser.set_defaults(
        contract_closure_gate=None,
        contract_closure_gate_lite=None,
        contract_closure_gate_lite_v1=None,
        contract_closure_gate_lite_rescue=None,
        contract_closure_gate_lite_rescue_plus=None,
        contract_closure_gate_v3=None,
        contract_closure_budget_control=None,
        adaptive_budget_v2=None,
        pre_submit_contract_audit=None,
        spec_adversarial_self_test=None,
        obligation_guided=None,
        cgvl=None,
    )
    run_agent_parser.add_argument(
        "--env-file",
        type=Path,
        help="dotenv-style file containing secrets such as FEATURELIFTBENCH_API_KEY",
    )
    run_agent_parser.add_argument("--yolo", action="store_true", help="pass --yolo to mini-swe-agent")
    run_agent_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=3600,
        help="maximum wall-clock seconds for each agent task run",
    )
    run_agent_parser.add_argument(
        "--num-workers",
        type=int,
        default=1,
        help="number of task runs to execute concurrently when input_path is a dataset root",
    )
    run_agent_parser.add_argument(
        "--agent-command",
        help=(
            "command template. --agent command placeholders: {workspace}, {task_file}, "
            "{submission_dir}, {agent_output_dir}. --agent openhands-agent additionally "
            "supports: {prompt_file}, {model}, {python}"
        ),
    )
    run_agent_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="disable live suite progress UI and print plain started/finished lines instead",
    )
    run_agent_parser.add_argument(
        "--agent-arg",
        action="append",
        default=[],
        help="extra argument appended to the agent command; may be repeated",
    )
    run_agent_parser.add_argument(
        "--task-id",
        action="append",
        dest="task_ids",
        help="limit suite run to specific task_id values; may be repeated",
    )
    run_agent_parser.add_argument(
        "--skip-completed",
        type=Path,
        help="deprecated alias: previous suite output directory; retains only passed tasks",
    )
    run_agent_parser.add_argument(
        "--resume",
        nargs="?",
        const=True,
        default=None,
        metavar="DIR",
        help="resume a suite run in --output (or DIR); retains non-retry statuses from existing suite.json",
    )
    run_agent_parser.add_argument(
        "--retry-only-status",
        default=None,
        help=(
            "comma-separated run statuses to re-run when using --resume "
            "(default: missing_submission,failed,not_evaluated)"
        ),
    )
    run_agent_parser.add_argument(
        "--extra-agent-passes",
        type=int,
        default=0,
        help="after the first suite pass, automatically re-run failed tasks up to N additional times",
    )
    run_agent_parser.add_argument(
        "--max-task-attempts",
        type=int,
        default=None,
        help="skip agent re-runs for tasks that already reached this many attempts",
    )
    run_agent_parser.add_argument(
        "--retry-rate-limit",
        type=int,
        default=1,
        help=(
            "when a task fails due to API rate limiting, retry up to this many total attempts "
            "(waits ~65s between tries to clear TPM windows; default: 1). "
            "Empty-submission protocol flakes also consult --retry-transient-api."
        ),
    )
    run_agent_parser.add_argument(
        "--retry-transient-api",
        type=int,
        default=3,
        help=(
            "when a task ends with an empty submission because of a retryable API/protocol "
            "error (OpenLux invalid_encrypted_content, rate limit, or promoted OpenHands "
            "tool validation), retry up to this many total attempts. Does not retry model "
            "failures that already produced a package. Default: 3"
        ),
    )
    run_agent_parser.add_argument(
        "--eval-docker",
        action="store_true",
        help="evaluate collected submissions inside the Docker eval image",
    )
    run_agent_parser.add_argument(
        "--eval-docker-image",
        default=DEFAULT_EVAL_IMAGE,
        help=(
            f"Docker image for --eval-docker "
            f"(default: {DEFAULT_EVAL_IMAGE}; Go tasks auto-use {DEFAULT_GO_EVAL_IMAGE})"
        ),
    )
    run_agent_parser.add_argument(
        "--agent-docker",
        action="store_true",
        help="run the agent itself inside the FeatureLiftBench agent Docker image",
    )
    run_agent_parser.add_argument(
        "--agent-docker-image",
        default=None,
        help=f"Docker image for --agent-docker (default: {DEFAULT_AGENT_IMAGE})",
    )

    setup_parser = subparsers.add_parser(
        "setup",
        help="validate flb.local.toml, Docker images, and LLM connectivity",
    )
    setup_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_LOCAL_CONFIG,
        help="local experiment config (default: flb.local.toml)",
    )
    setup_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print resolved runtime policy without running checks",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="run a suite from flb.local.toml (preflight, agent, eval, analysis)",
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_LOCAL_CONFIG,
        help="local experiment config (default: flb.local.toml)",
    )
    run_parser.add_argument(
        "--suite",
        choices=["sanity", "smoke", "pilot5", "main", "custom"],
        help="override [run].suite from config",
    )
    run_parser.add_argument("--max-steps", type=int, help="override [agent].max_steps")
    run_parser.add_argument("--workers", type=int, help="override [run].workers")
    run_parser.add_argument("--output", type=Path, help="override output directory")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print resolved plan without running",
    )

    resume_parser = subparsers.add_parser(
        "resume",
        help="resume a previous featureliftbench run output directory",
    )
    resume_parser.add_argument("output_dir", type=Path)
    resume_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_LOCAL_CONFIG,
        help="local experiment config (default: flb.local.toml)",
    )
    resume_parser.add_argument(
        "--suite",
        choices=["sanity", "smoke", "pilot5", "main", "custom"],
        help="override [run].suite from config",
    )
    resume_parser.add_argument("--max-steps", type=int, help="override [agent].max_steps")
    resume_parser.add_argument("--workers", type=int, help="override [run].workers")
    resume_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print resolved plan without running",
    )

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="run smoke suite (1-task OpenHands + eval gate)",
    )
    smoke_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_LOCAL_CONFIG,
        help="local experiment config (default: flb.local.toml)",
    )
    smoke_parser.add_argument("--max-steps", type=int, help="override [agent].max_steps")
    smoke_parser.add_argument("--workers", type=int, help="override [run].workers")
    smoke_parser.add_argument("--output", type=Path, help="override output directory")
    smoke_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print resolved plan without running",
    )

    add_catalog_parser(subparsers)

    args = parser.parse_args(argv)

    if args.command == "validate-task":
        return _cmd_validate_task(args)
    if args.command == "validate-benchmark":
        return _cmd_validate_benchmark(args)
    if args.command == "render-task":
        return _cmd_render_task(args)
    if args.command == "migrate-task-spec":
        return _cmd_migrate_task_spec(args)
    if args.command == "annotate-spec-status":
        return _cmd_annotate_spec_status(args)
    if args.command == "eval":
        return _cmd_eval(args)
    if args.command == "score":
        return _cmd_score(args)
    if args.command == "run-agent":
        return _cmd_run_agent(args)
    if args.command == "setup":
        return _cmd_setup(args)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "resume":
        return _cmd_resume(args)
    if args.command == "smoke":
        return _cmd_smoke(args)
    if args.command == "catalog":
        return dispatch_catalog(args)

    parser.error(f"unknown command: {args.command}")
    return 2


def _cmd_validate_task(args: argparse.Namespace) -> int:
    result = validate_task(args.task_dir)

    if args.json:
        payload = {
            "task_dir": str(result.task_dir),
            "task_id": result.task_id,
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif result.valid:
        print(f"valid task: {result.task_id}")
        for warning in result.warnings:
            print(f"warning: {warning}")
    else:
        print(f"invalid task: {args.task_dir}", file=sys.stderr)
        for error in result.errors:
            print(f"- {error}", file=sys.stderr)
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)

    return 0 if result.valid else 1


def _cmd_validate_benchmark(args: argparse.Namespace) -> int:
    from .agent_config import _read_env_file
    from .benchmark_gate import (
        DEFAULT_ORACLE_SUMMARY,
        DEFAULT_UPSTREAM_DIRECT_SUMMARY,
        GateRunOptions,
        MEETS,
        reviewer_config_from_environment,
        run_benchmark_gate,
    )

    try:
        if args.api_review and args.agent_review:
            raise ValueError("choose either --api-review or --agent-review, not both")
        reviewer = None
        if args.api_review or args.agent_review:
            reviewer = reviewer_config_from_environment(
                model=args.review_model,
                api_base=args.review_api_base,
                api_key_env=args.review_api_key_env,
                timeout_seconds=args.review_timeout_seconds,
                env_values=_read_env_file(args.review_env_file),
                mode="agent" if args.agent_review else "one_shot",
                max_output_tokens=args.review_max_output_tokens,
                reasoning_effort=args.review_reasoning_effort,
                agent_max_turns=args.agent_max_turns,
                agent_max_total_tokens=args.agent_max_total_tokens,
                agent_pending_only=not args.agent_review_all_selected,
            )
        payload = run_benchmark_gate(
            GateRunOptions(
                benchmark=args.benchmark,
                output=args.output,
                task_ids=tuple(args.task_id),
                source_materialization=not args.no_source_materialization,
                oracle_summary=args.oracle_summary or DEFAULT_ORACLE_SUMMARY,
                upstream_direct_summary=(
                    args.upstream_direct_summary or DEFAULT_UPSTREAM_DIRECT_SUMMARY
                ),
                adjudications=args.adjudications,
                reviewer=reviewer,
                private_evaluator_policy_acknowledged=(
                    args.acknowledge_private_evaluator_policy
                ),
            )
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    summary = {
        "benchmark": payload["benchmark"],
        "task_count": payload["task_count"],
        "label_counts": payload["label_counts"],
        "output": payload["output"],
        "selection_written": False,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.require_pass and payload["label_counts"].get(MEETS) != payload["task_count"]:
        return 1
    return 0


def _load_task_metadata(task_dir: Path) -> dict:
    metadata_path = task_dir / "metadata.json"
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _cmd_render_task(args: argparse.Namespace) -> int:
    metadata = _load_task_metadata(args.task_dir)
    rendered = render_public_task(metadata)
    if args.write:
        (args.task_dir / "TASK.md").write_text(rendered, encoding="utf-8")
        print(f"wrote {args.task_dir / 'TASK.md'}")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")
    return 0


def _cmd_migrate_task_spec(args: argparse.Namespace) -> int:
    try:
        payload = migrate_task_to_compliant(args.task_dir, dry_run=args.dry_run)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        action = "validated" if args.dry_run else "migrated"
        print(f"{action} {payload['task_id']}")
        print(f"spec_hash={payload['spec_hash']}")
    return 0


def _cmd_annotate_spec_status(args: argparse.Namespace) -> int:
    updated = 0
    for task_dir in sorted(path for path in args.tasks_root.iterdir() if path.is_dir()):
        if not (task_dir / "metadata.json").is_file():
            continue
        if annotate_legacy_status(task_dir, dry_run=args.dry_run):
            updated += 1
            print(task_dir.name)
    print(f"annotated={updated} dry_run={args.dry_run}")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    use_docker = args.docker or os.environ.get("FEATURELIFTBENCH_EVAL_DOCKER", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if use_docker:
        result = evaluate_submission_docker(
            args.task_dir,
            args.submission_dir,
            args.output,
            image=args.docker_image,
            use_docker=True,
        )
    else:
        result = evaluate_submission(
            args.task_dir,
            args.submission_dir,
            args.output,
            functional_only=args.functional_only,
            trusted_capsule=args.trusted_evaluation_capsule,
            isolation_context=(
                {
                    "source_filesystem_absent": True,
                    "network_disabled": True,
                    "mount_allowlist_pass": True,
                    "verification_mode": "trusted_capsule_pending_host_verification",
                }
                if args.functional_only and args.trusted_evaluation_capsule
                else None
            ),
        )
    result_path = args.output / "result.json"
    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"wrote result: {result_path}", file=sys.stderr)
    return 0 if result["status"] == "passed" else 1


def _cmd_score(args: argparse.Namespace) -> int:
    try:
        data = json.loads(args.result_json.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"cannot read result file: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"invalid result JSON: {exc}", file=sys.stderr)
        return 1

    scores = data.get("scores")
    if not isinstance(scores, dict):
        print("result JSON does not contain scores", file=sys.stderr)
        return 1

    print(json.dumps(scores, indent=2, sort_keys=True))
    return 0


def _cmd_run_agent(args: argparse.Namespace) -> int:
    from .agent_adapters import AgentRunConfig
    from .agent_config import load_agent_run_config
    from .agent_runner import run_agent_on_path
    from .suite_utils import parse_retry_only_statuses

    base_config = AgentRunConfig(
        agent=args.agent,
        agent_bin=args.agent_bin,
        model=args.model,
        config=args.config,
        yolo=args.yolo,
        timeout_seconds=args.timeout_seconds,
        command=args.agent_command,
        extra_args=tuple(args.agent_arg or []),
    )
    try:
        loaded_config = load_agent_run_config(
            base_config=base_config,
            config_path=args.agent_config,
            profile_name=args.agent_profile,
            env_file=args.env_file,
            mount_public_tests=args.mount_public_tests,
            prompt_style=args.prompt_style,
            expose_source_hints=args.expose_source_hints,
            source_context=args.source_context,
            td_cognition=args.td_cognition,
            exec_contract=args.exec_contract,
            exec_contract_variant=args.exec_contract_variant,
            self_contract=args.self_contract,
            test_first_lift=args.test_first_lift,
            contract_closure_gate=args.contract_closure_gate,
            contract_closure_gate_lite=args.contract_closure_gate_lite,
            contract_closure_gate_lite_v1=args.contract_closure_gate_lite_v1,
            contract_closure_gate_lite_rescue=(
                args.contract_closure_gate_lite_rescue
            ),
            contract_closure_gate_lite_rescue_plus=(
                args.contract_closure_gate_lite_rescue_plus
            ),
            contract_closure_gate_v3=args.contract_closure_gate_v3,
            contract_closure_budget_control=args.contract_closure_budget_control,
            adaptive_budget_v2=args.adaptive_budget_v2,
            pre_submit_contract_audit=args.pre_submit_contract_audit,
            spec_adversarial_self_test=args.spec_adversarial_self_test,
            obligation_guided=args.obligation_guided,
            cgvl=args.cgvl,
        )
        resume_dir, resume_mode = _resolve_resume_args(args)
        retry_only_statuses = parse_retry_only_statuses(args.retry_only_status)
        eval_docker = args.eval_docker or _env_truthy("FEATURELIFTBENCH_EVAL_DOCKER")
        agent_docker = args.agent_docker or _env_truthy("FEATURELIFTBENCH_AGENT_DOCKER")
        agent_docker_image = (
            args.agent_docker_image
            or os.environ.get("FEATURELIFTBENCH_AGENT_DOCKER_IMAGE", "").strip()
            or DEFAULT_AGENT_IMAGE
        )
        result = run_agent_on_path(
            resolve_task_input(args.input_path),
            args.output,
            loaded_config.run_config,
            agent_config_summary=loaded_config.summary,
            num_workers=args.num_workers,
            progress=not args.no_progress,
            task_ids=args.task_ids or None,
            skip_completed_dir=args.skip_completed,
            retry_rate_limit=args.retry_rate_limit,
            retry_transient_api=args.retry_transient_api,
            resume_dir=resume_dir,
            resume_mode=resume_mode,
            retry_only_statuses=retry_only_statuses,
            extra_agent_passes=args.extra_agent_passes,
            max_task_attempts=args.max_task_attempts,
            eval_docker=eval_docker,
            eval_docker_image=args.eval_docker_image,
            agent_docker=agent_docker,
            agent_docker_image=agent_docker_image,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("mode") == "suite":
        return 0 if result.get("summary", {}).get("failed") == 0 else 1
    return 0 if result.get("status") == "passed" else 1


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _resolve_resume_args(args: argparse.Namespace) -> tuple[Path | None, bool]:
    if args.resume is not None:
        if args.resume is True:
            return args.output.resolve(), True
        return Path(args.resume).resolve(), True
    return None, False


def _cmd_setup(args: argparse.Namespace) -> int:
    from .run_workflow import cmd_setup

    try:
        return cmd_setup(config_path=args.config, dry_run=args.dry_run)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _cmd_run(args: argparse.Namespace) -> int:
    from .run_workflow import cmd_run

    try:
        result = cmd_run(
            config_path=args.config,
            suite=args.suite,
            max_steps=args.max_steps,
            workers=args.workers,
            output_dir=str(args.output) if args.output else None,
            dry_run=args.dry_run,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not result.dry_run:
        print(f"Done: {result.output_dir}", file=sys.stderr)
    return result.exit_code


def _cmd_resume(args: argparse.Namespace) -> int:
    from .run_workflow import cmd_run

    try:
        result = cmd_run(
            config_path=args.config,
            resume_dir=args.output_dir.resolve(),
            suite=args.suite,
            max_steps=args.max_steps,
            workers=args.workers,
            dry_run=args.dry_run,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not result.dry_run:
        print(f"Done: {result.output_dir}", file=sys.stderr)
    return result.exit_code


def _cmd_smoke(args: argparse.Namespace) -> int:
    from .run_workflow import cmd_run

    try:
        result = cmd_run(
            config_path=args.config,
            suite="smoke",
            max_steps=args.max_steps,
            workers=args.workers,
            output_dir=str(args.output) if args.output else None,
            dry_run=args.dry_run,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not result.dry_run:
        print(f"Done: {result.output_dir}", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
