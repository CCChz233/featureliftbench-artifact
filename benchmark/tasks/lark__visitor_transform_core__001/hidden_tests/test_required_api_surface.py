"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Lark,
    Tree,
    Transformer,
    Visitor,
    v_args,
    Discard,
)


def test_required_api_surface():
    assert isinstance(Lark, type)
    assert hasattr(Lark, 'parse')
    assert isinstance(Tree, type)
    assert isinstance(Transformer, type)
    assert hasattr(Transformer, 'transform')
    assert isinstance(Visitor, type)
    assert callable(v_args)
    assert Discard is not None
