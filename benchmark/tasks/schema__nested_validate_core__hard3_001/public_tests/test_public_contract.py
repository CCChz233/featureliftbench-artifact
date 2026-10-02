
from featurelifted import Schema


def test_schema_validates_nested_dict():
    validator = Schema({"name": str, "age": int})
    assert validator.validate({"name": "Ada", "age": 2}) == {"name": "Ada", "age": 2}
