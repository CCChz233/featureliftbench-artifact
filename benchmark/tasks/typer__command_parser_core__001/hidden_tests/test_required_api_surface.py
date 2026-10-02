"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    testing,
)


def test_required_api_surface():
    assert testing is not None
    assert isinstance(getattr(testing, 'CliRunner'), type)
    assert hasattr(getattr(testing, 'CliRunner'), 'invoke')
