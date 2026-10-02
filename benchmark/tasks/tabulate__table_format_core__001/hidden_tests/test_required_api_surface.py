"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    tabulate,
    tabulate_formats,
    simple_separated_format,
)


def test_required_api_surface():
    assert callable(tabulate)
    assert tabulate_formats is not None
    assert callable(simple_separated_format)
