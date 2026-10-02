"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    errors,
    markup,
    text,
)


def test_required_api_surface():
    assert errors is not None
    assert issubclass(getattr(errors, 'MarkupError'), BaseException)
    assert markup is not None
    assert callable(getattr(markup, 'escape'))
    assert callable(getattr(markup, 'render'))
    assert text is not None
    assert isinstance(getattr(text, 'Text'), type)
    assert hasattr(getattr(text, 'Text'), 'from_markup')
    assert getattr(text, 'Text') is not None
    assert getattr(text, 'Text') is not None
    assert getattr(text, 'Text') is not None
