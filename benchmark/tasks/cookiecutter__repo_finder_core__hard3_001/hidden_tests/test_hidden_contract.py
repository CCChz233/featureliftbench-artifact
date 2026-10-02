
import pytest

from featurelifted import RepoFinder, UnsafePathError, safe_join


def test_replay_override():
    finder = RepoFinder()
    result = finder.find_template("demo", replay={"demo": "local/demo"})
    assert result["expanded"] == "local/demo"
    assert result["replay_used"] is True


def test_nested_template_detection():
    finder = RepoFinder()
    result = finder.find_template("nested/{{cookiecutter.project_slug}}/cookiecutter.json")
    assert result["nested"] is True


def test_safe_join_rejects_parent_segments():
    with pytest.raises(UnsafePathError):
        safe_join("/templates", "..", "escape")
