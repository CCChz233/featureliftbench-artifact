from featurelifted import DictLoader
from featurelifted import Environment
from featurelifted.loaders import BaseLoader


MULTI = {
    "layout": "|{% block a %}A{% endblock %}{% block b %}B{% endblock %}|",
    "mid": '{% extends "layout" %}{% block a %}a{% endblock %}',
    "leaf": '{% extends "mid" %}{% block b %}b{% endblock %}',
}


def test_multi_level_inheritance() -> None:
    env = Environment(loader=DictLoader(MULTI), trim_blocks=True)
    assert env.get_template("leaf").render() == "|ab|"


def test_loader_module_required_for_missing_template() -> None:
    from featurelifted.exceptions import TemplateNotFound

    env = Environment(loader=DictLoader({}))
    try:
        env.get_template("missing")
    except TemplateNotFound as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected TemplateNotFound")


def test_base_loader_subclass_get_source() -> None:
    class OneShot(BaseLoader):
        def get_source(self, environment, template):
            return "static", None, lambda: True

    env = Environment(loader=OneShot())
    assert env.get_template("x").render() == "static"
