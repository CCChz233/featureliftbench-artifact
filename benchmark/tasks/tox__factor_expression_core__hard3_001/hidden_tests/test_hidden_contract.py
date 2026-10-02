
from featurelifted import filter_for_env


def test_filter_for_env_by_factors():
    value = "py: included\n!py: excluded\nlinux: also\nmac: skip"
    result = filter_for_env(value, env_name=None, env_factors={"py", "linux"})
    assert "included" in result
    assert "also" in result
    assert "excluded" not in result
    assert "skip" not in result
