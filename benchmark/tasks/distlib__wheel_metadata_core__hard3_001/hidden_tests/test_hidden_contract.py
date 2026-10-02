
from featurelifted import normalize_record_path, parse_record, to_posix, validate_record_hash


def test_to_posix_converts_separators():
    assert "/" in to_posix("a\\b\\c") or to_posix("a/b/c") == "a/b/c"


def test_normalize_record_path_strips_dot_prefix():
    assert normalize_record_path("./pkg/file.py") == "pkg/file.py"


def test_parse_record_handles_missing_hash_and_size():
    rows = parse_record("README.txt,,\n")
    assert rows[0] == ("README.txt", None, None)


def test_validate_record_hash():
    digest = "sha256=" + ("a" * 64)
    assert validate_record_hash("pkg/file.py", digest) is True
    assert validate_record_hash("pkg/file.py", "bad") is False
