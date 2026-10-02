
from featurelifted import normalize_project_metadata


def test_normalize_project_metadata():
    project = {
        "name": "My Package",
        "dependencies": ["requests>=2", "click>=8"],
        "classifiers": ["License :: OSI Approved :: MIT License"],
    }
    normalized = normalize_project_metadata(project)
    assert normalized["name"] == "my-package"
    assert normalized["dependencies"] == ["click>=8", "requests>=2"]
