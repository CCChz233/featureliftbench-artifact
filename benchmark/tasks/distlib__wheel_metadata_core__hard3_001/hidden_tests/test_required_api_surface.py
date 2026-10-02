"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    to_posix,
    normalize_record_path,
    parse_record,
    validate_record_hash,
)


def test_required_api_surface():
    assert callable(to_posix)
    assert callable(normalize_record_path)
    assert callable(parse_record)
    assert callable(validate_record_hash)
