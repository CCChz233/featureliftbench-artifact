
from featurelifted import FSOpenerRegistry, parse_fs_url


def test_parse_fs_url_and_open():
    scheme, path, params = parse_fs_url("mem://bucket/dir?readonly=true")
    assert scheme == "mem"
    assert params["readonly"] == "true"

    registry = FSOpenerRegistry(default_protocol="mem")

    @registry.register("mem")
    def open_mem(params):
        return {"params": params}

    fs, subpath = registry.open("mem://bucket/dir?readonly=true")
    assert fs["params"]["readonly"] == "true"
    assert subpath is None
