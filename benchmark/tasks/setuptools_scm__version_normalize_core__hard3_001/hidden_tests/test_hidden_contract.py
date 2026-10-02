
from featurelifted import version_from_scm


def test_distance_adds_dev_suffix():
    version = version_from_scm(".", tag="1.0.0", distance=3, dirty=False, node="abc")
    assert version.startswith("1.0.1.dev3+")


def test_dirty_adds_local_suffix():
    version = version_from_scm(".", tag="1.0.0", distance=0, dirty=True, node="1234567")
    assert "1234567" in version
    assert "dirty" in version.lower()


def test_node_normalization():
    version = version_from_scm(".", tag="2.0.0", distance=1, dirty=False, node="abcdef0")
    assert "abcdef0" in version
