
import pytest

from featurelifted import BaseModel, ValidationError, field_validator


class Versioned(BaseModel):
    version: str

    @field_validator("version", mode="before")
    def normalize(value):
        return str(value).lstrip("v")


def test_before_validator_normalizes():
    obj = Versioned(version="v1.2")
    assert obj.version == "1.2"


def test_validation_error_on_after_failure():
    class Strict(BaseModel):
        age: int

        @field_validator("age", mode="after")
        def positive(value):
            if value < 0:
                raise ValueError("must be positive")
            return value

    with pytest.raises(ValidationError) as exc:
        Strict(age=-1)
    assert exc.value.errors[0]["field"] == "age"
