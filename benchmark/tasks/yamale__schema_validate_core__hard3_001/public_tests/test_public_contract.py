
from featurelifted import make_schema, validate


def test_basic_schema_validation():
    schema = make_schema("name: str\nage: int\n")
    results = validate(schema, [({"name": "Ada", "age": 2}, "doc")], _raise_error=False)
    assert results[0].isValid()
