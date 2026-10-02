from __future__ import annotations

import pytest

from featurelifted import InvalidRequirement
from featurelifted import Marker
from featurelifted import Requirement
from featurelifted import SpecifierSet
from featurelifted import Version
from featurelifted import default_environment


def test_versions_and_specifiers_basic_semantics() -> None:
    assert Version("1.0a1") < Version("1.0")
    assert Version("1!2.0") > Version("2.0")
    assert str(Version("  v1.0-1 ")) == "1.0.post1"

    spec = SpecifierSet(">=1.0,<2.0")
    assert Version("1.5") in spec
    assert Version("2.0") not in spec
    assert list(spec.filter(["0.9", "1.0", "1.5", "2.0"])) == ["1.0", "1.5"]


def test_requirements_and_markers_public_api() -> None:
    req = Requirement('demo[fast]>=1.0; python_version >= "3.10"')

    assert req.name == "demo"
    assert req.extras == {"fast"}
    assert str(req.specifier) == ">=1.0"
    assert req.marker is not None
    assert req.marker.evaluate({"python_version": "3.11"})
    assert not req.marker.evaluate({"python_version": "3.9"})

    env = default_environment()
    assert "python_version" in env
    assert Marker('os_name == "posix" or python_version >= "4"').evaluate(
        {"os_name": "posix", "python_version": "3.11"}
    )


def test_invalid_requirement_is_rejected() -> None:
    with pytest.raises(InvalidRequirement):
        Requirement("not a valid requirement !!!")
