from __future__ import annotations

from featurelifted import (
    is_valid_filename,
    is_valid_filepath,
    sanitize_filename,
    sanitize_filepath,
    validate_filename,
    validate_filepath,
)


def test_sanitize_filename_replaces_invalid_chars() -> None:
    assert sanitize_filename("foo:bar", replacement_text="_") == "foo_bar"
    validate_filename("foo_bar")
    assert is_valid_filename("foo_bar")


def test_sanitize_filepath_joins_segments() -> None:
    sanitized = sanitize_filepath("dir/sub:name/file.txt", replacement_text="-")
    assert sanitized == "dir/sub-name/file.txt"
    validate_filepath(sanitized)
    assert is_valid_filepath(sanitized)


def test_validate_filename_accepts_simple_name() -> None:
    validate_filename("report.csv")
    assert is_valid_filename("report.csv")
