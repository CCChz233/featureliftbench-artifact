
from featurelifted import T, glom


def test_glom_path_and_t():
    target = {"user": {"name": "Ada"}}
    assert glom(target, "user.name") == "Ada"
    assert glom(target, T) is target
