
import pytest

from featurelifted import MetadataValidationError, normalize_project_metadata, select_environment


def test_select_environment_inheritance():
    envs = {
        "base": {"dependencies": ["requests"]},
        "test": {"extends": "base", "scripts": {"pytest": "pytest"}},
    }
    resolved = select_environment(envs, "test")
    assert resolved["dependencies"] == ["requests"]
    assert resolved["scripts"]["pytest"] == "pytest"


def test_circular_environment_raises():
    envs = {"a": {"extends": "b"}, "b": {"extends": "a"}}
    with pytest.raises(ValueError, match="circular"):
        select_environment(envs, "a")


def test_invalid_classifier_raises():
    with pytest.raises(MetadataValidationError):
        normalize_project_metadata({"classifiers": ["Not A Real Classifier"]})
