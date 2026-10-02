from __future__ import annotations

import pytest

from featurelifted import InvalidMarker
from featurelifted import InvalidRequirement
from featurelifted import InvalidSpecifier
from featurelifted import InvalidVersion
from featurelifted import Marker
from featurelifted import Requirement
from featurelifted import Specifier
from featurelifted import SpecifierSet
from featurelifted import Version
from featurelifted import default_environment


def test_version_normalization_ordering_and_invalid_inputs() -> None:
    assert str(Version("1.0.dev1")) == "1.0.dev1"
    assert str(Version("1.0rc1")) == "1.0rc1"
    assert str(Version("1.0+ABC.5")) == "1.0+abc.5"
    assert Version("1.0.dev1") < Version("1.0a1") < Version("1.0") < Version("1.0.post1")
    assert Version("1.0+abc.5") > Version("1.0")
    assert hash(Version("1.0")) == hash(Version("1.0.0"))

    with pytest.raises(InvalidVersion):
        Version("1..0")


def test_specifier_prerelease_wildcard_compatible_and_filtering() -> None:
    assert Version("1.0a1") not in SpecifierSet(">=1.0")
    assert Version("1.0a1") in SpecifierSet(">=1.0a1")
    assert Version("1.2.5") in SpecifierSet("==1.2.*")
    assert Version("1.3.0") not in SpecifierSet("==1.2.*")
    assert Version("2.3.4") in SpecifierSet("~=2.2")
    assert Version("3.0") not in SpecifierSet("~=2.2")
    assert Version("1.4") not in SpecifierSet(">=1.0,!=1.4,<2.0")
    assert str(Specifier("~=2.2")) == "~=2.2"

    filtered = list(SpecifierSet(">=1.0,<2.0").filter(["0.9", "1.1", "1.4", "2.0"]))
    assert filtered == ["1.1", "1.4"]

    with pytest.raises(InvalidSpecifier):
        SpecifierSet("=>1.0")


def test_requirement_urls_extras_and_marker_evaluation() -> None:
    req = Requirement(
        'Example_Pkg[PDF,ssl] ~=1.4 ; python_version >= "3.10" and extra == "PDF"'
    )

    assert req.name == "Example_Pkg"
    assert req.extras == {"PDF", "ssl"}
    assert str(req.specifier) == "~=1.4"
    assert req.url is None
    assert req.marker is not None
    assert req.marker.evaluate({"python_version": "3.11", "extra": "PDF"})
    assert not req.marker.evaluate({"python_version": "3.9", "extra": "PDF"})
    assert not req.marker.evaluate({"python_version": "3.11", "extra": "ssl"})

    url_req = Requirement('demo @ https://example.com/demo-1.0.tar.gz ; os_name == "posix"')
    assert url_req.name == "demo"
    assert url_req.url == "https://example.com/demo-1.0.tar.gz"
    assert url_req.marker is not None
    assert url_req.marker.evaluate({"os_name": "posix"})

    with pytest.raises(InvalidRequirement):
        Requirement("demo[bad extra]>=1")


def test_marker_boolean_logic_default_environment_and_errors() -> None:
    env = default_environment()
    assert env["implementation_name"]
    assert env["python_version"].count(".") == 1

    marker = Marker(
        '(python_version >= "3.8" and implementation_name in "cpython,pypy") '
        'or os_name == "nt"'
    )
    assert marker.evaluate(
        {
            "python_version": "3.12",
            "implementation_name": "cpython",
            "os_name": "posix",
        }
    )
    assert not marker.evaluate(
        {
            "python_version": "3.7",
            "implementation_name": "cpython",
            "os_name": "posix",
        }
    )

    with pytest.raises(InvalidMarker):
        Marker('python_version => "3.10"')
