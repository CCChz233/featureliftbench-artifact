
from featurelifted import parse_project_dependencies, resolve_group


def test_parse_main_and_optional_groups():
    project = {
        "dependencies": {"requests": ">=2"},
        "optional-dependencies": {"dev": ["pytest>=7"]},
    }
    groups = parse_project_dependencies(project)
    assert "main" in groups
    assert groups["dev"].optional is True
    assert resolve_group("dev", groups)[0].name == "pytest"
