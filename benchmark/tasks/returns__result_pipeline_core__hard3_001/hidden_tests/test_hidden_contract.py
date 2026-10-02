
from featurelifted import Failure, Success, safe


def test_failure_short_circuits():
    result = Failure("boom").map(lambda x: x + 1).bind(lambda x: Success(x))
    assert isinstance(result, Failure)
    assert result.failure == "boom"


@safe
def divide(a, b):
    return a / b


def test_safe_decorator_maps_exceptions():
    ok = divide(4, 2)
    bad = divide(1, 0)
    assert isinstance(ok, Success)
    assert ok.value == 2
    assert isinstance(bad, Failure)
    assert isinstance(bad.failure, ZeroDivisionError)
