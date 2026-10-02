"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Environment,
    DictLoader,
    exceptions,
    loaders,
)


def test_required_api_surface():
    assert isinstance(Environment, type)
    assert hasattr(Environment, 'get_template')
    assert isinstance(DictLoader, type)
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'TemplateNotFound'), BaseException)
    assert loaders is not None
    assert isinstance(getattr(loaders, 'BaseLoader'), type)
