import sys

from featurelifted import EvalContext
from featurelifted import Mark
from featurelifted import evaluate_condition


def test_string_condition_true() -> None:
    ctx = EvalContext()
    mark = Mark("skipif", {"reason": "win32"})
    result, reason = evaluate_condition(ctx, mark, "sys.platform == 'win32'")
    assert result == (sys.platform == "win32")
    assert reason == "win32"


def test_boolean_condition() -> None:
    ctx = EvalContext()
    mark = Mark("skipif", {"reason": "disabled"})
    assert evaluate_condition(ctx, mark, True) == (True, "disabled")
