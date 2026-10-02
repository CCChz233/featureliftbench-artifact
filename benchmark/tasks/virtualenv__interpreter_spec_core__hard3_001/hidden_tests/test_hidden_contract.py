
import pytest

from featurelifted import InvalidInterpreterSpec, discover_paths, match_version, parse_spec


def test_match_version_operators():
    assert match_version("3.11.2", ">=3.11")
    assert not match_version("3.10.0", ">=3.11")
    assert match_version("3.11.1", "~=3.11.0")


def test_version_constraint_filters_candidates():
    candidates = discover_paths(
        ["/opt/python3.10/bin/python3.10", "/opt/python3.11/bin/python3.11"],
        "python>=3.11",
    )
    assert candidates == ["/opt/python3.11/bin/python3.11"]


def test_invalid_spec_raises():
    with pytest.raises(InvalidInterpreterSpec):
        parse_spec("not a spec !!!")
