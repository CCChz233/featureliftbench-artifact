from featurelifted import Environment
from featurelifted import filters
from featurelifted import tests as jinja_tests


def test_default_filter_with_boolean() -> None:
    env = Environment()
    tmpl = env.from_string("{{ false|default('no', true) }}")
    assert tmpl.render() == "no"


def test_defined_test_in_template() -> None:
    from featurelifted.runtime import Undefined

    env = Environment()
    assert env.call_test("defined", 1) is True
    assert env.call_test("undefined", Undefined()) is True
    assert env.call_test("even", 4) is True


def test_filters_module_required_for_join() -> None:
    env = Environment()
    assert env.call_filter("join", ["a", "b"], ":") == "a:b"
    assert "join" in filters.FILTERS


def test_tests_module_required_for_even() -> None:
    env = Environment()
    assert env.call_test("even", 4) is True
    assert "even" in jinja_tests.TESTS
