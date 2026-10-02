
import pytest

from featurelifted import CIMultiDict, CIMultiDictProxy, MultiDict


def test_popone_and_popall_semantics():
    md = MultiDict()
    md.add("k", 1)
    md.add("k", 2)
    assert md.popone("k") == 2
    assert md["k"] == 1
    assert md.popall("k") == [1]
    with pytest.raises(KeyError):
        md.popall("missing")


def test_cimultidict_case_insensitive_lookup_and_equality():
    md = CIMultiDict()
    md.add("Header", "v1")
    assert md["header"] == "v1"
    other = CIMultiDict([("HEADER", "v1")])
    assert md == other


def test_cimultidict_proxy_reflects_base():
    base = CIMultiDict()
    proxy = CIMultiDictProxy(base)
    proxy.add("A", 1)
    assert base.getall("a") == [1]
