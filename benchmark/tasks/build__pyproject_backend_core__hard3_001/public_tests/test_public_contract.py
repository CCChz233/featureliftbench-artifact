
from featurelifted import parse_build_system_table


def test_default_build_system_when_missing():
    table = parse_build_system_table({})
    assert table["build-backend"] == "setuptools.build_meta"
    assert "setuptools" in table["requires"][0]
