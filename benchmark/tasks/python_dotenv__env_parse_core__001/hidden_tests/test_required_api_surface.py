"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    dotenv_values,
    set_key,
    get_key,
)


def test_required_api_surface():
    assert callable(dotenv_values)
    assert callable(set_key)
    assert callable(get_key)
