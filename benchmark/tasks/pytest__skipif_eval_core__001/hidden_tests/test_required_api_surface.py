"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Mark,
    EvalContext,
    evaluate_condition,
)


def test_required_api_surface():
    assert isinstance(Mark, type)
    assert isinstance(EvalContext, type)
    assert callable(evaluate_condition)
