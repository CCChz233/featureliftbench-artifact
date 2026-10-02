
from featurelifted import Dict, Int, String


def test_dict_validates_schema():
    schema = Dict({"name": String(), "age": Int()})
    assert schema.check({"name": "Ada", "age": 2}) == {"name": "Ada", "age": 2}
