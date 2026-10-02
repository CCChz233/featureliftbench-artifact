from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest

from featurelifted import Duration, ISO8601Error, duration_isoformat, parse_duration


def test_parse_duration_full_components() -> None:
    result = parse_duration("P1Y2M3DT4H5M6S")
    assert isinstance(result, Duration)
    assert result.years == 1
    assert result.months == 2
    assert result.tdelta.days == 3
    assert result.tdelta.seconds == 4 * 3600 + 5 * 60 + 6


def test_parse_duration_comma_decimal_hours() -> None:
    result = parse_duration("PT1,5H")
    assert result == timedelta(hours=1, minutes=30)


def test_duration_totimedelta_with_start() -> None:
    from featurelifted.isodates import parse_date

    d = Duration(years=1, months=1)
    td = d.totimedelta(start=parse_date("2000-03-01"))
    assert td == timedelta(days=396)


def test_duration_isoformat_timedelta() -> None:
    assert duration_isoformat(timedelta(hours=2, minutes=30)) == "PT2H30M"


def test_parse_invalid_raises() -> None:
    with pytest.raises(ISO8601Error):
        parse_duration("not-a-duration")


def test_no_isodate_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from isodate|import isodate)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        assert not import_pattern.search(path.read_text(encoding="utf-8"))
