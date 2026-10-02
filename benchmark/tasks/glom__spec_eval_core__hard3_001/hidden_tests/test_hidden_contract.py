
import pytest

from featurelifted import Coalesce, PathAccessError, glom


def test_coalesce_and_default():
    target = {"a": 1}
    assert glom(target, Coalesce(["missing", "a"], default=0)) == 1
    assert glom(target, "missing", default="fallback") == "fallback"


def test_nested_path_error():
    with pytest.raises(PathAccessError):
        glom({"a": {}}, "a.b.c")
