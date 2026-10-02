
import pytest

from featurelifted import parse_project_dependencies, resolve_group


def test_dependency_group_includes():
    project = {
        "dependencies": {"requests": ">=2"},
        "dependency-groups": {
            "test": {"dependencies": ["pytest>=7"], "include-group": ["lint"]},
            "lint": {"dependencies": ["ruff>=0.1"]},
        },
    }
    groups = parse_project_dependencies(project)
    names = [dep.name for dep in resolve_group("test", groups)]
    assert names == ["pytest", "ruff"]


def test_circular_include_group_raises():
    project = {
        "dependency-groups": {
            "a": {"include-group": ["b"]},
            "b": {"include-group": ["a"]},
        }
    }
    groups = parse_project_dependencies(project)
    with pytest.raises(ValueError, match="circular"):
        resolve_group("a", groups)
