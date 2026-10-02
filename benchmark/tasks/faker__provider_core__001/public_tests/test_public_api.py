from __future__ import annotations

from featurelifted import Faker


def test_en_us_person_address_and_phone_are_seeded() -> None:
    fake = Faker("en_US")
    fake.seed_instance(12345)
    name = fake.name()
    address = fake.address()
    phone = fake.phone_number()
    assert isinstance(name, str) and " " in name
    assert isinstance(address, str) and "\n" in address
    assert phone.startswith("(") or phone[0].isdigit()

    fake.seed_instance(12345)
    assert fake.name() == name
    assert fake.address() == address
    assert fake.phone_number() == phone
