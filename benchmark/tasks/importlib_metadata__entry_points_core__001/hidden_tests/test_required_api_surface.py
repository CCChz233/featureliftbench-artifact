"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    EntryPoint,
    EntryPoints,
    PathDistribution,
    Sectioned,
)


def test_required_api_surface():
    assert isinstance(EntryPoint, type)
    assert EntryPoint is not None
    assert EntryPoint is not None
    assert EntryPoint is not None
    assert EntryPoint is not None
    assert isinstance(EntryPoints, type)
    assert hasattr(EntryPoints, 'select')
    assert hasattr(EntryPoints, '__getitem__')
    assert isinstance(PathDistribution, type)
    assert PathDistribution is not None
    assert isinstance(Sectioned, type)
    assert hasattr(Sectioned, 'section_pairs')
