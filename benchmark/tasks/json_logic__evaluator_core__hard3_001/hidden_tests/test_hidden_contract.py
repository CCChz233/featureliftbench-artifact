from featurelifted import jsonLogic


def test_short_circuit_and():
    rule = {"and": [False, {"/": [1, 0]}]}
    assert jsonLogic(rule, {}) is False


def test_nested_var_path_and_missing():
    rule = {"var": "user.name"}
    assert jsonLogic(rule, {"user": {"name": "Ada"}}) == "Ada"
    assert jsonLogic(rule, {}) is None


def test_or_short_circuit():
    assert jsonLogic({"or": [True, {"/": [1, 0]}]}, {}) is True
