"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    DeepDiff,
    parse_path,
    extract,
)


def test_required_api_surface():
    assert isinstance(DeepDiff, type)
    assert hasattr(DeepDiff, 'get')
    assert hasattr(DeepDiff, '__contains__')
    assert callable(parse_path)
    assert callable(extract)
