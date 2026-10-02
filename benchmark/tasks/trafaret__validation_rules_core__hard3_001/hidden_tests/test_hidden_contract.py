
import pytest

from featurelifted import And, DataError, Dict, Forward, Int, Key, Or, String


def test_or_composition():
    validator = Or(Int(), String())
    assert validator.check("x") == "x"
    assert validator.check(1) == 1
    assert And(String(), String()).check("hi") == "hi"


def test_key_optional_and_dataerror_path():
    schema = Dict({"name": String()})
    with pytest.raises(DataError) as exc:
        schema.check({})
    assert exc.value.path == ("name",)


def test_forward_recursion():
    node = Forward()
    node.set_type(Dict({"value": Int(), "next": Or(node, String())}))
    data = {"value": 1, "next": {"value": 2, "next": "done"}}
    assert node.check(data)["next"]["next"] == "done"
