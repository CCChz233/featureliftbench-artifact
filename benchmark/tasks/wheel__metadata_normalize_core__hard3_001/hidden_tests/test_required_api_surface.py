"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    safe_name,
    safe_extra,
    split_sections,
    parse_wheel_filename,
    urlsafe_b64encode,
    WheelError,
)


def test_required_api_surface():
    assert callable(safe_name)
    assert callable(safe_extra)
    assert callable(split_sections)
    assert callable(parse_wheel_filename)
    assert callable(urlsafe_b64encode)
    assert issubclass(WheelError, BaseException)
