
from featurelifted import find_envs


def test_find_envs_brace_groups():
    assert set(find_envs("{lint,test}-py")) == {"lint-py", "test-py"}
