
import pytest

from featurelifted import find_dist_info, parse_wheel_record, script_name


def test_find_dist_info_unique():
    names = ["pkg/__init__.py", "demo-1.0.dist-info/METADATA"]
    assert find_dist_info(names) == "demo-1.0.dist-info"


def test_multiple_dist_info_raises():
    names = ["a-1.dist-info/METADATA", "b-2.dist-info/RECORD"]
    with pytest.raises(ValueError):
        find_dist_info(names)


def test_script_name_from_entry_point():
    assert script_name("pkg.module:main") == "main"
    assert script_name("pkg.module:Class.method") == "Class"
