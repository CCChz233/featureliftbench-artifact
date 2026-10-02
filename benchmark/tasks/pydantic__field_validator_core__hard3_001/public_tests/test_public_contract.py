
from featurelifted import BaseModel, field_validator


class User(BaseModel):
    name: str

    @field_validator("name", mode="after")
    def strip_name(value):
        return value.strip()


def test_after_validator_strips():
    user = User(name="  ada  ")
    assert user.name == "ada"
