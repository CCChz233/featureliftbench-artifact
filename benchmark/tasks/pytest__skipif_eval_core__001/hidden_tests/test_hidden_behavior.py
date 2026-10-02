import sys

from featurelifted import EvalContext
from featurelifted import Mark
from featurelifted import evaluate_condition


def test_markeval_namespace_merged() -> None:
    ctx = EvalContext(markeval_namespace=[{"flag": True}])
    mark = Mark("skipif", {})
    result, _ = evaluate_condition(ctx, mark, "flag")
    assert result is True


def test_obj_globals_merged() -> None:
    ctx = EvalContext(obj_globals={"value": 42})
    mark = Mark("skipif", {})
    result, _ = evaluate_condition(ctx, mark, "value == 42")
    assert result is True


def test_invalid_syntax_raises() -> None:
    import pytest

    ctx = EvalContext()
    mark = Mark("skipif", {})
    with pytest.raises(Exception):
        evaluate_condition(ctx, mark, "1 and")
