"""Equal-budget, no-checker control for Contract Closure Gate experiments."""

from __future__ import annotations


CONTROL_ENV = "FEATURELIFTBENCH_CONTRACT_CLOSURE_BUDGET_CONTROL"
CONTROL_PHASE_ENV = "FEATURELIFTBENCH_CONTRACT_CLOSURE_CONTROL_PHASE"
DEFAULT_PRIMARY_TOKEN_LIMIT = 2_000_000
DEFAULT_PRIMARY_MAX_STEPS = 45


def task_appendix() -> str:
    """Add a generic review instruction without machine-readable gate feedback."""

    return (
        "## Equal-Budget Implementation Review\n\n"
        "After implementing the feature, spend a final review pass checking the public "
        "Required Output API and behavior requirements against your implementation. "
        "Check for missing modules, objects, members, signatures, exceptions, and "
        "forbidden dependencies. Run ordinary local checks that you judge useful, then "
        "finish the submission. No contract checker or evaluator feedback is available "
        "in this control arm.\n"
    )

def openhands_appendix() -> str:
    """Mirror the generic review instruction in the OpenHands wrapper prompt."""

    return (
        "Implement the submission, then perform one ordinary final review against the "
        "public task: look for missing APIs, members, signatures, exceptions, and "
        "forbidden dependencies. Use normal repository inspection or local checks only. "
        "There is no contract checker or evaluator feedback in this control arm.\n"
    )
