from featurelifted import Expression


def test_empty_expression_is_false() -> None:
    assert not Expression.compile("").evaluate(lambda name: True)


def test_and_or_logic() -> None:
    matcher = {"fast": True, "slow": False}.__getitem__
    assert Expression.compile("fast and not slow").evaluate(matcher)
