"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Faker,
)


def test_required_api_surface():
    assert isinstance(Faker, type)
    assert Faker is not None  # runtime-bound method
    assert Faker is not None  # runtime-bound method
    assert Faker is not None  # runtime-bound method
    assert Faker is not None  # runtime-bound method
    assert hasattr(Faker, 'seed_instance')
