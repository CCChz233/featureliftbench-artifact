"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    define,
    field,
    validate,
    validators,
)


def test_required_api_surface():
    assert callable(define)
    assert callable(field)
    assert callable(validate)
    assert validators is not None
    assert callable(getattr(validators, 'and_'))
    assert callable(getattr(validators, 'deep_iterable'))
    assert callable(getattr(validators, 'deep_mapping'))
    assert callable(getattr(validators, 'ge'))
    assert callable(getattr(validators, 'instance_of'))
    assert callable(getattr(validators, 'matches_re'))
    assert callable(getattr(validators, 'min_len'))
    assert callable(getattr(validators, 'optional'))
    assert callable(getattr(validators, 'set_disabled'))
