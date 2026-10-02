from featurelifted import DictLoader
from featurelifted import Environment


LAYOUT = "|{% block body %}base{% endblock %}|"
CHILD = '{% extends "layout" %}{% block body %}child{% endblock %}'


def test_extends_overrides_block() -> None:
    env = Environment(
        loader=DictLoader({"layout": LAYOUT, "child": CHILD}),
        trim_blocks=True,
    )
    assert env.get_template("child").render() == "|child|"
