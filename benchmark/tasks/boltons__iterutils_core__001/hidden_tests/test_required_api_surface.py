"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    chunked,
    windowed,
    pairwise,
    unique,
    bucketize,
    remap,
    get_path,
    partition,
    iterutils,
)


def test_required_api_surface():
    assert callable(chunked)
    assert callable(windowed)
    assert callable(pairwise)
    assert callable(unique)
    assert callable(bucketize)
    assert callable(remap)
    assert callable(get_path)
    assert callable(partition)
    assert iterutils is not None
    assert callable(getattr(iterutils, 'backoff'))
    assert callable(getattr(iterutils, 'chunk_ranges'))
