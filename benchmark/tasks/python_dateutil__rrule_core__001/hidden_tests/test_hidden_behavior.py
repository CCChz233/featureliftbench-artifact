from __future__ import annotations

import datetime
import re
from pathlib import Path

import pytest

from featurelifted import DAILY, FR, MONTHLY, YEARLY, rrule, rruleset, rrulestr


def test_bysetpos_last_friday() -> None:
    start = datetime.datetime(2020, 1, 1)
    rule = rrule(MONTHLY, dtstart=start, byweekday=FR(-1), count=3)
    got = list(rule)
    assert all(d.weekday() == 4 for d in got)
    assert got[0] == datetime.datetime(2020, 1, 31)
    assert got[1] == datetime.datetime(2020, 2, 28)


def test_byeaster_occurrence() -> None:
    start = datetime.datetime(2020, 1, 1)
    rule = rrule(YEARLY, dtstart=start, byeaster=1, count=2)
    got = list(rule)
    assert len(got) == 2
    assert got[0].month == 4 and got[0].day == 13  # Easter Monday 2020


def test_rruleset_exdate_skips() -> None:
    start = datetime.datetime(2020, 1, 1)
    rs = rruleset()
    rs.rrule(rrule(DAILY, dtstart=start, count=3))
    rs.exdate(datetime.datetime(2020, 1, 2))
    assert list(rs) == [
        datetime.datetime(2020, 1, 1),
        datetime.datetime(2020, 1, 3),
    ]


def test_invalid_rrulestr_freq_raises() -> None:
    start = datetime.datetime(2020, 1, 1)
    with pytest.raises(ValueError):
        rrulestr("RRULE:FREQ=NOTAFREQ;COUNT=1", dtstart=start, ignoretz=True)


def test_rrulestr_byday_token() -> None:
    start = datetime.datetime(2020, 1, 1)
    rule = rrulestr("RRULE:FREQ=MONTHLY;BYDAY=1MO;COUNT=2", dtstart=start, ignoretz=True)
    got = list(rule)
    assert len(got) == 2
    assert got[0].weekday() == 0


def test_no_dateutil_import_surface() -> None:
    import featurelifted

    forbidden = {"parser", "tz", "relativedelta", "zoneinfo"}
    exports = set(getattr(featurelifted, "__all__", []))
    for name in forbidden:
        assert name not in exports, f"unexpected export: {name}"

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from dateutil|import dateutil)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))
