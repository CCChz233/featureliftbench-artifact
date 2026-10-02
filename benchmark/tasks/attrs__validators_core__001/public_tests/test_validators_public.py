from __future__ import annotations

import pytest

from featurelifted import define, field, validate
from featurelifted import validators as v


@define
class User:
    name: str = field(validator=v.instance_of(str))
    age: int = field(validator=v.and_(v.instance_of(int), v.ge(18)))


def test_valid_instance_passes() -> None:
    user = User("Ada", 30)
    validate(user)
    assert user.name == "Ada"


def test_instance_of_rejects_wrong_type() -> None:
    with pytest.raises(TypeError):
        User(42, 30)
