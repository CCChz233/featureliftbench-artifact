"""Constitution API-surface coverage generated from public_spec."""

import featurelifted.zpt.template

from featurelifted import (
    TemplateError,
    zpt,
)


def test_required_api_surface():
    assert issubclass(TemplateError, BaseException)
    assert getattr(zpt, 'template') is not None
    assert isinstance(getattr(getattr(zpt, 'template'), 'PageTemplate'), type)
