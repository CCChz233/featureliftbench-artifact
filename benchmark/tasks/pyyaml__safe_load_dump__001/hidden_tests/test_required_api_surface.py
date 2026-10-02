"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    safe_load,
    safe_load_all,
    safe_dump,
    safe_dump_all,
    YAMLError,
    constructor,
)


def test_required_api_surface():
    assert callable(safe_load)
    assert callable(safe_load_all)
    assert callable(safe_dump)
    assert callable(safe_dump_all)
    assert issubclass(YAMLError, BaseException)
    assert constructor is not None
    assert issubclass(getattr(constructor, 'ConstructorError'), BaseException)
