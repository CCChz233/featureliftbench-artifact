"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse_wheel_record,
    find_dist_info,
    script_name,
)


def test_required_api_surface():
    assert callable(parse_wheel_record)
    assert callable(find_dist_info)
    assert callable(script_name)
