"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Post,
    parse,
    load,
    loads,
    dump,
    dumps,
    checks,
)


def test_required_api_surface():
    assert isinstance(Post, type)
    assert Post is not None
    assert Post is not None
    assert hasattr(Post, 'to_dict')
    assert hasattr(Post, '__getitem__')
    assert callable(parse)
    assert callable(load)
    assert callable(loads)
    assert callable(dump)
    assert callable(dumps)
    assert callable(checks)
