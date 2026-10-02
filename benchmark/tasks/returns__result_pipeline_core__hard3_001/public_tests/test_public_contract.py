
from featurelifted import Failure, Success


def test_success_map_and_bind():
    value = Success(2).map(lambda x: x + 1).bind(lambda x: Success(x * 3))
    assert isinstance(value, Success)
    assert value.value == 9
