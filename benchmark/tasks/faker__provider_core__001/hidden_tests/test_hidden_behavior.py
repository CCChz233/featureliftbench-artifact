from __future__ import annotations

import re

from featurelifted import Faker


def test_only_en_us_locale_and_provider_formats() -> None:
    fake = Faker("en_US")
    fake.seed_instance(99)
    phone = fake.phone_number()
    assert re.search(r"\d{3}", phone)
    assert len(phone) >= 10

    fake.seed_instance(7)
    first = fake.first_name()
    last = fake.last_name()
    assert first.isalpha()
    assert last.isalpha()

    fake.seed_instance(7)
    assert fake.first_name() == first
    assert fake.last_name() == last


def test_address_contains_city_state_zip_pattern() -> None:
    fake = Faker("en_US")
    fake.seed_instance(2024)
    address = fake.address()
    lines = address.split("\n")
    assert len(lines) >= 2
    assert any(char.isdigit() for char in lines[-1])
