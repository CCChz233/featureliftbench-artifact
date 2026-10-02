
import pytest

from featurelifted import WheelError, parse_wheel_filename, split_sections, urlsafe_b64encode


def test_split_sections_and_b64():
    sections = split_sections("readme\n\n[metadata]\nname=demo\n\n[files]\nREADME")
    assert sections[0][0] is None
    assert sections[0][1] == ["readme"]
    assert sections[1][0] == "metadata"
    assert urlsafe_b64encode(b"abc") == b"YWJj"


def test_parse_wheel_filename():
    name, version, build = parse_wheel_filename("my_pkg-1.0.0-py3-none-any.whl")
    assert name == "my-pkg"
    assert version == "1.0.0"
    with pytest.raises(WheelError):
        parse_wheel_filename("not-a-wheel.txt")
