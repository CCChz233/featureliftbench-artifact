
from featurelifted import version_from_scm


def test_version_from_tag():
    assert version_from_scm(".", tag="v1.2.3", distance=0, dirty=False) == "1.2.3"
