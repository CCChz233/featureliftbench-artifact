
from featurelifted import normalize_record_path, parse_record


def test_parse_record_row():
    rows = parse_record("pkg/__init__.py,sha256=abc,12\n")
    assert rows[0][0] == "pkg/__init__.py"
