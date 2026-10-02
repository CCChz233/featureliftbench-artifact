"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    rrule,
    rruleset,
    rrulestr,
    YEARLY,
    MONTHLY,
    WEEKLY,
    DAILY,
    MO,
    TU,
    WE,
    TH,
    FR,
    SA,
    SU,
)


def test_required_api_surface():
    assert rrule is not None
    assert callable(rruleset)
    assert callable(rrulestr)
    assert YEARLY is not None
    assert MONTHLY is not None
    assert WEEKLY is not None
    assert DAILY is not None
    assert MO is not None
    assert TU is not None
    assert WE is not None
    assert TH is not None
    assert FR is not None
    assert SA is not None
    assert SU is not None
