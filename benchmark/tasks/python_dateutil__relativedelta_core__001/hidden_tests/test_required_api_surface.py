"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    relativedelta,
    MO,
    TU,
    WE,
    TH,
    FR,
    SA,
    SU,
)


def test_required_api_surface():
    assert relativedelta is not None
    assert MO is not None
    assert TU is not None
    assert WE is not None
    assert TH is not None
    assert FR is not None
    assert SA is not None
    assert SU is not None
    assert getattr(MO, 'weekday') is not None
