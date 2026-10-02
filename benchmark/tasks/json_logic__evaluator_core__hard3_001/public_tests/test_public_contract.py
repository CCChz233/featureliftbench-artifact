
from featurelifted import jsonLogic

def test_simple_comparison_and_var():
    rule = {"==": [{"var": "x"}, 1]}
    assert jsonLogic(rule, {"x": 1}) is True
    assert jsonLogic(rule, {"x": 2}) is False

def test_numeric_plus():
    assert jsonLogic({"+": [1, "2", 3]}, {}) == 6

def test_if_operator():
    rule = {"if": [True, "yes", "no"]}
    assert jsonLogic(rule, {}) == "yes"
