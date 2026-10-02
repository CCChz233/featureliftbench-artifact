
from featurelifted import MultiDict, MultiDictProxy


def test_multidict_duplicate_keys_and_getall():
    md = MultiDict()
    md.add("a", 1)
    md.add("a", 2)
    assert md["a"] == 2
    assert md.getall("a") == [1, 2]


def test_proxy_reflects_base_mutations():
    base = MultiDict([("x", 1)])
    proxy = MultiDictProxy(base)
    proxy["x"] = 9
    assert base["x"] == 9
