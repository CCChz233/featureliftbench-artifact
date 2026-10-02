"""Agent experiment arms and their information-preserving method variants.

See docs/EXPERIMENT_ARMS.md. Semantic contract (API/behaviors/hidden) is unchanged.
Main is No-Hint by default; source-location hints require explicit opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


MOUNT_PUBLIC_TESTS_ENV = "FEATURELIFTBENCH_MOUNT_PUBLIC_TESTS"
PROMPT_STYLE_ENV = "FEATURELIFTBENCH_PROMPT_STYLE"
EXPOSE_SOURCE_HINTS_ENV = "FEATURELIFTBENCH_EXPOSE_SOURCE_HINTS"
SOURCE_CONTEXT_ENV = "FEATURELIFTBENCH_SOURCE_CONTEXT"
TD_COGNITION_ENV = "FEATURELIFTBENCH_TD_COGNITION"
EXEC_CONTRACT_ENV = "FEATURELIFTBENCH_EXEC_CONTRACT"
EXEC_CONTRACT_VARIANT_ENV = "FEATURELIFTBENCH_EXEC_CONTRACT_VARIANT"
SELF_CONTRACT_ENV = "FEATURELIFTBENCH_SELF_CONTRACT"
TEST_FIRST_LIFT_ENV = "FEATURELIFTBENCH_TEST_FIRST_LIFT"
CONTRACT_CLOSURE_GATE_ENV = "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE"
CONTRACT_CLOSURE_GATE_LITE_ENV = "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_LITE"
CONTRACT_CLOSURE_GATE_LITE_V1_ENV = (
    "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_LITE_V1_FROZEN"
)
CONTRACT_CLOSURE_GATE_LITE_RESCUE_ENV = (
    "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_LITE_RESCUE"
)
CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS_ENV = (
    "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS"
)
CONTRACT_CLOSURE_GATE_V3_ENV = "FEATURELIFTBENCH_CONTRACT_CLOSURE_GATE_V3"
CONTRACT_CLOSURE_BUDGET_CONTROL_ENV = (
    "FEATURELIFTBENCH_CONTRACT_CLOSURE_BUDGET_CONTROL"
)
ADAPTIVE_BUDGET_V2_ENV = "FEATURELIFTBENCH_ADAPTIVE_BUDGET_V2"
PRE_SUBMIT_CONTRACT_AUDIT_ENV = "FEATURELIFTBENCH_PRE_SUBMIT_CONTRACT_AUDIT"
SPEC_ADVERSARIAL_SELF_TEST_ENV = "FEATURELIFTBENCH_SPEC_ADVERSARIAL_SELF_TEST"
OBLIGATION_GUIDED_ENV = "FEATURELIFTBENCH_OBLIGATION_GUIDED"
CGVL_ENV = "FEATURELIFTBENCH_CGVL"
ABLATION_ARM_ENV = "FEATURELIFTBENCH_ABLATION_ARM"

PROMPT_STYLES = frozenset({"standard", "short"})
SOURCE_CONTEXTS = frozenset({"full_repository", "pruned_context", "contract_only"})
EXEC_CONTRACT_VARIANTS = frozenset(
    {"clean3", "cgcc_lite", "cgcc_roc", "cgcc_rmc", "fcec"}
)


@dataclass(frozen=True)
class AblationOptions:
    """Resolved ablation settings for one agent run."""

    mount_public_tests: bool = False
    prompt_style: str = "standard"
    expose_source_hints: bool = False
    source_context: str = "full_repository"
    td_cognition: bool = False
    exec_contract: bool = False
    exec_contract_variant: str = "clean3"
    self_contract: bool = False
    test_first_lift: bool = False
    contract_closure_gate: bool = False
    contract_closure_gate_lite: bool = False
    contract_closure_gate_lite_v1: bool = False
    contract_closure_gate_lite_rescue: bool = False
    contract_closure_gate_lite_rescue_plus: bool = False
    contract_closure_gate_v3: bool = False
    contract_closure_budget_control: bool = False
    adaptive_budget_v2: bool = False
    pre_submit_contract_audit: bool = False
    spec_adversarial_self_test: bool = False
    obligation_guided: bool = False
    cgvl: bool = False

    def __post_init__(self) -> None:
        style = str(self.prompt_style or "standard").strip().lower()
        if style not in PROMPT_STYLES:
            raise ValueError(f"prompt_style must be one of {sorted(PROMPT_STYLES)}, got {self.prompt_style!r}")
        object.__setattr__(self, "prompt_style", style)
        source_context = str(self.source_context or "full_repository").strip().lower()
        if source_context not in SOURCE_CONTEXTS:
            raise ValueError(
                f"source_context must be one of {sorted(SOURCE_CONTEXTS)}, "
                f"got {self.source_context!r}"
            )
        object.__setattr__(self, "source_context", source_context)
        if source_context == "contract_only" and bool(self.expose_source_hints):
            raise ValueError(
                "source_context='contract_only' cannot be combined with source-location hints"
            )
        object.__setattr__(self, "td_cognition", bool(self.td_cognition))
        object.__setattr__(self, "exec_contract", bool(self.exec_contract))
        exec_contract_variant = str(
            self.exec_contract_variant or "clean3"
        ).strip().lower()
        if exec_contract_variant not in EXEC_CONTRACT_VARIANTS:
            raise ValueError(
                "exec_contract_variant must be one of "
                f"{sorted(EXEC_CONTRACT_VARIANTS)}, got {self.exec_contract_variant!r}"
            )
        object.__setattr__(self, "exec_contract_variant", exec_contract_variant)
        object.__setattr__(self, "self_contract", bool(self.self_contract))
        object.__setattr__(self, "test_first_lift", bool(self.test_first_lift))
        object.__setattr__(
            self, "contract_closure_gate", bool(self.contract_closure_gate)
        )
        object.__setattr__(
            self,
            "contract_closure_gate_lite",
            bool(self.contract_closure_gate_lite),
        )
        object.__setattr__(
            self,
            "contract_closure_gate_lite_v1",
            bool(self.contract_closure_gate_lite_v1),
        )
        object.__setattr__(
            self,
            "contract_closure_gate_lite_rescue",
            bool(self.contract_closure_gate_lite_rescue),
        )
        object.__setattr__(
            self,
            "contract_closure_gate_lite_rescue_plus",
            bool(self.contract_closure_gate_lite_rescue_plus),
        )
        object.__setattr__(
            self,
            "contract_closure_gate_v3",
            bool(self.contract_closure_gate_v3),
        )
        object.__setattr__(
            self,
            "contract_closure_budget_control",
            bool(self.contract_closure_budget_control),
        )
        object.__setattr__(self, "adaptive_budget_v2", bool(self.adaptive_budget_v2))
        object.__setattr__(
            self,
            "pre_submit_contract_audit",
            bool(self.pre_submit_contract_audit),
        )
        object.__setattr__(
            self,
            "spec_adversarial_self_test",
            bool(self.spec_adversarial_self_test),
        )
        object.__setattr__(
            self,
            "obligation_guided",
            bool(self.obligation_guided),
        )
        object.__setattr__(self, "cgvl", bool(self.cgvl))
        method_arms = sum(
            1
            for flag in (
                self.td_cognition,
                self.exec_contract,
                self.self_contract,
                self.test_first_lift,
                self.contract_closure_gate,
                self.contract_closure_gate_lite,
                self.contract_closure_gate_lite_v1,
                self.contract_closure_gate_lite_rescue,
                self.contract_closure_gate_lite_rescue_plus,
                self.contract_closure_gate_v3,
                self.contract_closure_budget_control,
                self.adaptive_budget_v2,
                self.pre_submit_contract_audit,
                self.spec_adversarial_self_test,
                self.obligation_guided,
                self.cgvl,
            )
            if flag
        )
        if method_arms > 1:
            raise ValueError(
                "td_cognition, exec_contract, self_contract, test_first_lift, and "
                "contract_closure_gate, contract_closure_gate_lite, "
                "contract_closure_gate_lite_v1, contract_closure_gate_lite_rescue, "
                "contract_closure_gate_lite_rescue_plus, "
                "contract_closure_gate_v3, contract_closure_budget_control, "
                "adaptive_budget_v2, pre_submit_contract_audit, "
                "spec_adversarial_self_test, obligation_guided, and cgvl "
                "are mutually exclusive"
            )

    @property
    def ablation_arm(self) -> str:
        if self.cgvl:
            return "cgvl"
        if self.obligation_guided:
            return "obligation_guided"
        if self.spec_adversarial_self_test:
            return "spec_adversarial_self_test"
        if self.pre_submit_contract_audit:
            return "pre_submit_contract_audit"
        if self.adaptive_budget_v2:
            return "adaptive_budget_v2"
        if self.contract_closure_budget_control:
            return "contract_closure_budget_control"
        if self.contract_closure_gate_lite_v1:
            return "contract_closure_gate_lite_v1_frozen"
        if self.contract_closure_gate_lite_rescue:
            return "contract_closure_gate_lite_rescue"
        if self.contract_closure_gate_lite_rescue_plus:
            return "contract_closure_gate_lite_rescue_plus"
        if self.contract_closure_gate_v3:
            return "contract_closure_gate_v3"
        if self.contract_closure_gate_lite:
            return "contract_closure_gate_lite"
        if self.contract_closure_gate:
            return "contract_closure_gate"
        if self.test_first_lift:
            return "test_first_lift"
        if self.self_contract:
            return "self_contract"
        if self.exec_contract:
            if self.exec_contract_variant in {
                "cgcc_lite",
                "cgcc_roc",
                "cgcc_rmc",
                "fcec",
            }:
                return self.exec_contract_variant
            return "exec_contract"
        if self.td_cognition:
            return "td_cognition"
        parts: list[str] = []
        if self.expose_source_hints:
            parts.append("entrypoint_hint")
        if self.mount_public_tests:
            parts.append("public_feedback")
        if self.prompt_style == "short":
            parts.append("short_prompt")
        if self.source_context == "pruned_context":
            parts.append("pruned_context")
        if self.source_context == "contract_only":
            parts.append("contract_only")
        return "_".join(parts) if parts else "main"

    def to_env(self) -> dict[str, str]:
        return {
            MOUNT_PUBLIC_TESTS_ENV: "1" if self.mount_public_tests else "0",
            PROMPT_STYLE_ENV: self.prompt_style,
            EXPOSE_SOURCE_HINTS_ENV: "1" if self.expose_source_hints else "0",
            SOURCE_CONTEXT_ENV: self.source_context,
            TD_COGNITION_ENV: "1" if self.td_cognition else "0",
            EXEC_CONTRACT_ENV: "1" if self.exec_contract else "0",
            EXEC_CONTRACT_VARIANT_ENV: self.exec_contract_variant,
            SELF_CONTRACT_ENV: "1" if self.self_contract else "0",
            TEST_FIRST_LIFT_ENV: "1" if self.test_first_lift else "0",
            CONTRACT_CLOSURE_GATE_ENV: "1" if self.contract_closure_gate else "0",
            CONTRACT_CLOSURE_GATE_LITE_ENV: (
                "1" if self.contract_closure_gate_lite else "0"
            ),
            CONTRACT_CLOSURE_GATE_LITE_V1_ENV: (
                "1" if self.contract_closure_gate_lite_v1 else "0"
            ),
            CONTRACT_CLOSURE_GATE_LITE_RESCUE_ENV: (
                "1" if self.contract_closure_gate_lite_rescue else "0"
            ),
            CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS_ENV: (
                "1" if self.contract_closure_gate_lite_rescue_plus else "0"
            ),
            CONTRACT_CLOSURE_GATE_V3_ENV: (
                "1" if self.contract_closure_gate_v3 else "0"
            ),
            CONTRACT_CLOSURE_BUDGET_CONTROL_ENV: (
                "1" if self.contract_closure_budget_control else "0"
            ),
            ADAPTIVE_BUDGET_V2_ENV: "1" if self.adaptive_budget_v2 else "0",
            PRE_SUBMIT_CONTRACT_AUDIT_ENV: (
                "1" if self.pre_submit_contract_audit else "0"
            ),
            SPEC_ADVERSARIAL_SELF_TEST_ENV: (
                "1" if self.spec_adversarial_self_test else "0"
            ),
            OBLIGATION_GUIDED_ENV: "1" if self.obligation_guided else "0",
            CGVL_ENV: "1" if self.cgvl else "0",
            ABLATION_ARM_ENV: self.ablation_arm,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "ablation_arm": self.ablation_arm,
            "mount_public_tests": self.mount_public_tests,
            "prompt_style": self.prompt_style,
            "expose_source_hints": self.expose_source_hints,
            "source_context": self.source_context,
            "td_cognition": self.td_cognition,
            "exec_contract": self.exec_contract,
            "exec_contract_variant": self.exec_contract_variant,
            "self_contract": self.self_contract,
            "test_first_lift": self.test_first_lift,
            "contract_closure_gate": self.contract_closure_gate,
            "contract_closure_gate_lite": self.contract_closure_gate_lite,
            "contract_closure_gate_lite_v1": self.contract_closure_gate_lite_v1,
            "contract_closure_gate_lite_rescue": (
                self.contract_closure_gate_lite_rescue
            ),
            "contract_closure_gate_lite_rescue_plus": (
                self.contract_closure_gate_lite_rescue_plus
            ),
            "contract_closure_gate_v3": self.contract_closure_gate_v3,
            "contract_closure_budget_control": self.contract_closure_budget_control,
            "adaptive_budget_v2": self.adaptive_budget_v2,
            "pre_submit_contract_audit": self.pre_submit_contract_audit,
            "spec_adversarial_self_test": self.spec_adversarial_self_test,
            "obligation_guided": self.obligation_guided,
            "cgvl": self.cgvl,
        }


def ablation_options_from_env(env: Mapping[str, str] | None = None) -> AblationOptions:
    """Parse options from an environment mapping (empty → test-blind Main)."""

    values = env or {}
    mount_raw = str(values.get(MOUNT_PUBLIC_TESTS_ENV, "0")).strip().lower()
    mount = mount_raw not in {"0", "false", "no", "off"}
    style = str(values.get(PROMPT_STYLE_ENV, "standard")).strip().lower() or "standard"
    hints_raw = str(values.get(EXPOSE_SOURCE_HINTS_ENV, "0")).strip().lower()
    expose_hints = hints_raw not in {"0", "false", "no", "off"}
    source_context = (
        str(values.get(SOURCE_CONTEXT_ENV, "full_repository")).strip().lower()
        or "full_repository"
    )
    td_raw = str(values.get(TD_COGNITION_ENV, "0")).strip().lower()
    td_cognition = td_raw not in {"0", "false", "no", "off", ""}
    ec_raw = str(values.get(EXEC_CONTRACT_ENV, "0")).strip().lower()
    exec_contract = ec_raw not in {"0", "false", "no", "off", ""}
    exec_contract_variant = (
        str(values.get(EXEC_CONTRACT_VARIANT_ENV, "clean3")).strip().lower()
        or "clean3"
    )
    sc_raw = str(values.get(SELF_CONTRACT_ENV, "0")).strip().lower()
    self_contract = sc_raw not in {"0", "false", "no", "off", ""}
    tfl_raw = str(values.get(TEST_FIRST_LIFT_ENV, "0")).strip().lower()
    test_first_lift = tfl_raw not in {"0", "false", "no", "off", ""}
    ccg_raw = str(values.get(CONTRACT_CLOSURE_GATE_ENV, "0")).strip().lower()
    contract_closure_gate = ccg_raw not in {"0", "false", "no", "off", ""}
    ccg_lite_raw = str(
        values.get(CONTRACT_CLOSURE_GATE_LITE_ENV, "0")
    ).strip().lower()
    contract_closure_gate_lite = ccg_lite_raw not in {
        "0",
        "false",
        "no",
        "off",
        "",
    }
    ccg_lite_v1_raw = str(
        values.get(CONTRACT_CLOSURE_GATE_LITE_V1_ENV, "0")
    ).strip().lower()
    contract_closure_gate_lite_v1 = ccg_lite_v1_raw not in {
        "0",
        "false",
        "no",
        "off",
        "",
    }
    ccg_lite_rescue_raw = str(
        values.get(CONTRACT_CLOSURE_GATE_LITE_RESCUE_ENV, "0")
    ).strip().lower()
    contract_closure_gate_lite_rescue = ccg_lite_rescue_raw not in {
        "0",
        "false",
        "no",
        "off",
        "",
    }
    ccg_lite_rescue_plus_raw = str(
        values.get(CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS_ENV, "0")
    ).strip().lower()
    contract_closure_gate_lite_rescue_plus = ccg_lite_rescue_plus_raw not in {
        "0",
        "false",
        "no",
        "off",
        "",
    }
    ccg_v3_raw = str(values.get(CONTRACT_CLOSURE_GATE_V3_ENV, "0")).strip().lower()
    contract_closure_gate_v3 = ccg_v3_raw not in {
        "0",
        "false",
        "no",
        "off",
        "",
    }
    ccg_control_raw = str(
        values.get(CONTRACT_CLOSURE_BUDGET_CONTROL_ENV, "0")
    ).strip().lower()
    contract_closure_budget_control = ccg_control_raw not in {
        "0",
        "false",
        "no",
        "off",
        "",
    }
    v2_raw = str(values.get(ADAPTIVE_BUDGET_V2_ENV, "0")).strip().lower()
    adaptive_budget_v2 = v2_raw not in {"0", "false", "no", "off", ""}
    audit_raw = str(values.get(PRE_SUBMIT_CONTRACT_AUDIT_ENV, "0")).strip().lower()
    pre_submit_contract_audit = audit_raw not in {"0", "false", "no", "off", ""}
    sa_raw = str(values.get(SPEC_ADVERSARIAL_SELF_TEST_ENV, "0")).strip().lower()
    spec_adversarial_self_test = sa_raw not in {"0", "false", "no", "off", ""}
    og_raw = str(values.get(OBLIGATION_GUIDED_ENV, "0")).strip().lower()
    obligation_guided = og_raw not in {"0", "false", "no", "off", ""}
    cgvl_raw = str(values.get(CGVL_ENV, "0")).strip().lower()
    cgvl = cgvl_raw not in {"0", "false", "no", "off", ""}
    return AblationOptions(
        mount_public_tests=mount,
        prompt_style=style,
        expose_source_hints=expose_hints,
        source_context=source_context,
        td_cognition=td_cognition,
        exec_contract=exec_contract,
        exec_contract_variant=exec_contract_variant,
        self_contract=self_contract,
        test_first_lift=test_first_lift,
        contract_closure_gate=contract_closure_gate,
        contract_closure_gate_lite=contract_closure_gate_lite,
        contract_closure_gate_lite_v1=contract_closure_gate_lite_v1,
        contract_closure_gate_lite_rescue=contract_closure_gate_lite_rescue,
        contract_closure_gate_lite_rescue_plus=(
            contract_closure_gate_lite_rescue_plus
        ),
        contract_closure_gate_v3=contract_closure_gate_v3,
        contract_closure_budget_control=contract_closure_budget_control,
        adaptive_budget_v2=adaptive_budget_v2,
        pre_submit_contract_audit=pre_submit_contract_audit,
        spec_adversarial_self_test=spec_adversarial_self_test,
        obligation_guided=obligation_guided,
        cgvl=cgvl,
    )


def resolve_ablation_options(
    *,
    profile: Mapping[str, Any] | None = None,
    env_values: Mapping[str, str] | None = None,
    process_env: Mapping[str, str] | None = None,
    mount_public_tests: bool | None = None,
    prompt_style: str | None = None,
    expose_source_hints: bool | None = None,
    source_context: str | None = None,
    td_cognition: bool | None = None,
    exec_contract: bool | None = None,
    exec_contract_variant: str | None = None,
    self_contract: bool | None = None,
    test_first_lift: bool | None = None,
    contract_closure_gate: bool | None = None,
    contract_closure_gate_lite: bool | None = None,
    contract_closure_gate_lite_v1: bool | None = None,
    contract_closure_gate_lite_rescue: bool | None = None,
    contract_closure_gate_lite_rescue_plus: bool | None = None,
    contract_closure_gate_v3: bool | None = None,
    contract_closure_budget_control: bool | None = None,
    adaptive_budget_v2: bool | None = None,
    pre_submit_contract_audit: bool | None = None,
    spec_adversarial_self_test: bool | None = None,
    obligation_guided: bool | None = None,
    cgvl: bool | None = None,
) -> AblationOptions:
    """Resolve ablation with precedence: explicit CLI > process env > .env > profile > defaults."""

    profile = profile or {}
    env_values = env_values or {}
    process_env = process_env or {}

    if mount_public_tests is None:
        mount = _first_bool(
            process_env.get(MOUNT_PUBLIC_TESTS_ENV),
            env_values.get(MOUNT_PUBLIC_TESTS_ENV),
            profile.get("mount_public_tests"),
            default=False,
        )
    else:
        mount = bool(mount_public_tests)

    if prompt_style is None:
        style = _first_string(
            process_env.get(PROMPT_STYLE_ENV),
            env_values.get(PROMPT_STYLE_ENV),
            profile.get("prompt_style"),
            default="standard",
        )
    else:
        style = str(prompt_style).strip().lower()

    if expose_source_hints is None:
        expose_hints = _first_bool(
            process_env.get(EXPOSE_SOURCE_HINTS_ENV),
            env_values.get(EXPOSE_SOURCE_HINTS_ENV),
            profile.get("expose_source_hints"),
            default=False,
        )
    else:
        expose_hints = bool(expose_source_hints)

    if source_context is None:
        resolved_source_context = _first_string(
            process_env.get(SOURCE_CONTEXT_ENV),
            env_values.get(SOURCE_CONTEXT_ENV),
            profile.get("source_context"),
            default="full_repository",
        )
    else:
        resolved_source_context = str(source_context).strip().lower()

    if td_cognition is None:
        resolved_td = _first_bool(
            process_env.get(TD_COGNITION_ENV),
            env_values.get(TD_COGNITION_ENV),
            profile.get("td_cognition"),
            default=False,
        )
    else:
        resolved_td = bool(td_cognition)

    if exec_contract is None:
        resolved_ec = _first_bool(
            process_env.get(EXEC_CONTRACT_ENV),
            env_values.get(EXEC_CONTRACT_ENV),
            profile.get("exec_contract"),
            default=False,
        )
    else:
        resolved_ec = bool(exec_contract)

    if exec_contract_variant is None:
        resolved_ec_variant = _first_string(
            process_env.get(EXEC_CONTRACT_VARIANT_ENV),
            env_values.get(EXEC_CONTRACT_VARIANT_ENV),
            profile.get("exec_contract_variant"),
            default="clean3",
        )
    else:
        resolved_ec_variant = str(exec_contract_variant).strip().lower()

    if self_contract is None:
        resolved_sc = _first_bool(
            process_env.get(SELF_CONTRACT_ENV),
            env_values.get(SELF_CONTRACT_ENV),
            profile.get("self_contract"),
            default=False,
        )
    else:
        resolved_sc = bool(self_contract)

    if test_first_lift is None:
        resolved_tfl = _first_bool(
            process_env.get(TEST_FIRST_LIFT_ENV),
            env_values.get(TEST_FIRST_LIFT_ENV),
            profile.get("test_first_lift"),
            default=False,
        )
    else:
        resolved_tfl = bool(test_first_lift)

    if contract_closure_gate is None:
        resolved_ccg = _first_bool(
            process_env.get(CONTRACT_CLOSURE_GATE_ENV),
            env_values.get(CONTRACT_CLOSURE_GATE_ENV),
            profile.get("contract_closure_gate"),
            default=False,
        )
    else:
        resolved_ccg = bool(contract_closure_gate)

    if contract_closure_gate_lite is None:
        resolved_ccg_lite = _first_bool(
            process_env.get(CONTRACT_CLOSURE_GATE_LITE_ENV),
            env_values.get(CONTRACT_CLOSURE_GATE_LITE_ENV),
            profile.get("contract_closure_gate_lite"),
            default=False,
        )
    else:
        resolved_ccg_lite = bool(contract_closure_gate_lite)

    if contract_closure_gate_lite_v1 is None:
        resolved_ccg_lite_v1 = _first_bool(
            process_env.get(CONTRACT_CLOSURE_GATE_LITE_V1_ENV),
            env_values.get(CONTRACT_CLOSURE_GATE_LITE_V1_ENV),
            profile.get("contract_closure_gate_lite_v1"),
            default=False,
        )
    else:
        resolved_ccg_lite_v1 = bool(contract_closure_gate_lite_v1)

    if contract_closure_gate_lite_rescue is None:
        resolved_ccg_lite_rescue = _first_bool(
            process_env.get(CONTRACT_CLOSURE_GATE_LITE_RESCUE_ENV),
            env_values.get(CONTRACT_CLOSURE_GATE_LITE_RESCUE_ENV),
            profile.get("contract_closure_gate_lite_rescue"),
            default=False,
        )
    else:
        resolved_ccg_lite_rescue = bool(contract_closure_gate_lite_rescue)

    if contract_closure_gate_lite_rescue_plus is None:
        resolved_ccg_lite_rescue_plus = _first_bool(
            process_env.get(CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS_ENV),
            env_values.get(CONTRACT_CLOSURE_GATE_LITE_RESCUE_PLUS_ENV),
            profile.get("contract_closure_gate_lite_rescue_plus"),
            default=False,
        )
    else:
        resolved_ccg_lite_rescue_plus = bool(contract_closure_gate_lite_rescue_plus)

    if contract_closure_gate_v3 is None:
        resolved_ccg_v3 = _first_bool(
            process_env.get(CONTRACT_CLOSURE_GATE_V3_ENV),
            env_values.get(CONTRACT_CLOSURE_GATE_V3_ENV),
            profile.get("contract_closure_gate_v3"),
            default=False,
        )
    else:
        resolved_ccg_v3 = bool(contract_closure_gate_v3)

    if contract_closure_budget_control is None:
        resolved_ccg_control = _first_bool(
            process_env.get(CONTRACT_CLOSURE_BUDGET_CONTROL_ENV),
            env_values.get(CONTRACT_CLOSURE_BUDGET_CONTROL_ENV),
            profile.get("contract_closure_budget_control"),
            default=False,
        )
    else:
        resolved_ccg_control = bool(contract_closure_budget_control)

    if adaptive_budget_v2 is None:
        resolved_v2 = _first_bool(
            process_env.get(ADAPTIVE_BUDGET_V2_ENV),
            env_values.get(ADAPTIVE_BUDGET_V2_ENV),
            profile.get("adaptive_budget_v2"),
            default=False,
        )
    else:
        resolved_v2 = bool(adaptive_budget_v2)

    if pre_submit_contract_audit is None:
        resolved_pre_submit_audit = _first_bool(
            process_env.get(PRE_SUBMIT_CONTRACT_AUDIT_ENV),
            env_values.get(PRE_SUBMIT_CONTRACT_AUDIT_ENV),
            profile.get("pre_submit_contract_audit"),
            default=False,
        )
    else:
        resolved_pre_submit_audit = bool(pre_submit_contract_audit)

    if spec_adversarial_self_test is None:
        resolved_spec_adversarial = _first_bool(
            process_env.get(SPEC_ADVERSARIAL_SELF_TEST_ENV),
            env_values.get(SPEC_ADVERSARIAL_SELF_TEST_ENV),
            profile.get("spec_adversarial_self_test"),
            default=False,
        )
    else:
        resolved_spec_adversarial = bool(spec_adversarial_self_test)

    if obligation_guided is None:
        resolved_obligation_guided = _first_bool(
            process_env.get(OBLIGATION_GUIDED_ENV),
            env_values.get(OBLIGATION_GUIDED_ENV),
            profile.get("obligation_guided"),
            default=False,
        )
    else:
        resolved_obligation_guided = bool(obligation_guided)

    if cgvl is None:
        resolved_cgvl = _first_bool(
            process_env.get(CGVL_ENV),
            env_values.get(CGVL_ENV),
            profile.get("cgvl"),
            default=False,
        )
    else:
        resolved_cgvl = bool(cgvl)

    # An explicit positive CLI selection chooses that arm even when the profile
    # defaults to the sibling closure arm.
    if cgvl is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
        resolved_td = False
        resolved_ec = False
        resolved_sc = False
        resolved_tfl = False
    elif obligation_guided is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_td = False
        resolved_ec = False
        resolved_sc = False
        resolved_tfl = False
        resolved_cgvl = False
    elif spec_adversarial_self_test is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_obligation_guided = False
        resolved_td = False
        resolved_ec = False
        resolved_sc = False
        resolved_tfl = False
        resolved_cgvl = False
    elif pre_submit_contract_audit is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_td = False
        resolved_ec = False
        resolved_sc = False
        resolved_tfl = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
    elif adaptive_budget_v2 is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
    elif contract_closure_gate is True:
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
    elif contract_closure_gate_lite is True:
        resolved_ccg = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
    elif contract_closure_gate_lite_v1 is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
    elif contract_closure_gate_lite_rescue is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
    elif contract_closure_gate_lite_rescue_plus is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_v3 = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
    elif contract_closure_gate_v3 is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_control = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False
    elif contract_closure_budget_control is True:
        resolved_ccg = False
        resolved_ccg_lite = False
        resolved_ccg_lite_v1 = False
        resolved_ccg_lite_rescue = False
        resolved_ccg_lite_rescue_plus = False
        resolved_ccg_v3 = False
        resolved_v2 = False
        resolved_pre_submit_audit = False
        resolved_spec_adversarial = False
        resolved_obligation_guided = False

    if (
        obligation_guided is True
        or spec_adversarial_self_test is True
        or pre_submit_contract_audit is True
        or adaptive_budget_v2 is True
        or contract_closure_gate is True
        or contract_closure_gate_lite is True
        or contract_closure_gate_lite_v1 is True
        or contract_closure_gate_lite_rescue is True
        or contract_closure_gate_lite_rescue_plus is True
        or contract_closure_gate_v3 is True
        or contract_closure_budget_control is True
    ):
        resolved_cgvl = False

    return AblationOptions(
        mount_public_tests=mount,
        prompt_style=style,
        expose_source_hints=expose_hints,
        source_context=resolved_source_context,
        td_cognition=resolved_td,
        exec_contract=resolved_ec,
        exec_contract_variant=resolved_ec_variant,
        self_contract=resolved_sc,
        test_first_lift=resolved_tfl,
        contract_closure_gate=resolved_ccg,
        contract_closure_gate_lite=resolved_ccg_lite,
        contract_closure_gate_lite_v1=resolved_ccg_lite_v1,
        contract_closure_gate_lite_rescue=resolved_ccg_lite_rescue,
        contract_closure_gate_lite_rescue_plus=resolved_ccg_lite_rescue_plus,
        contract_closure_gate_v3=resolved_ccg_v3,
        contract_closure_budget_control=resolved_ccg_control,
        adaptive_budget_v2=resolved_v2,
        pre_submit_contract_audit=resolved_pre_submit_audit,
        spec_adversarial_self_test=resolved_spec_adversarial,
        obligation_guided=resolved_obligation_guided,
        cgvl=resolved_cgvl,
    )


def _first_string(*values: Any, default: str) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _first_bool(*values: Any, default: bool) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if not text:
            continue
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"invalid boolean ablation value: {value!r}")
    return default
