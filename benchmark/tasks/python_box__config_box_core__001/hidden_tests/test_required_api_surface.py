"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Box,
    ConfigBox,
    exceptions,
)


def test_required_api_surface():
    assert isinstance(Box, type)
    assert isinstance(ConfigBox, type)
    assert hasattr(ConfigBox, 'bool')
    assert hasattr(ConfigBox, 'float')
    assert hasattr(ConfigBox, 'getboolean')
    assert hasattr(ConfigBox, 'getfloat')
    assert hasattr(ConfigBox, 'int')
    assert hasattr(ConfigBox, 'list')
    assert exceptions is not None
    assert issubclass(getattr(exceptions, 'BoxKeyError'), BaseException)
