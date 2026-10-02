"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Selector,
    FakeElement,
    extract_text,
    SelectorSyntaxError,
)


def test_required_api_surface():
    assert isinstance(Selector, type)
    assert hasattr(Selector, 'css')
    assert hasattr(Selector, 'xpath')
    assert hasattr(Selector, 'register_namespace')
    assert hasattr(Selector, 'remove_namespace')
    assert hasattr(Selector, 'get')
    assert hasattr(Selector, 'getall')
    assert isinstance(FakeElement, type)
    assert callable(extract_text)
    assert issubclass(SelectorSyntaxError, BaseException)
