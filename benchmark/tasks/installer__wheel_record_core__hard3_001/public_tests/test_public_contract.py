
from featurelifted import parse_wheel_record


def test_parse_wheel_record_row():
    rows = parse_wheel_record("pkg/__init__.py,sha256=abc,12\n")
    assert rows[0] == ("pkg/__init__.py", "sha256=abc", 12)
