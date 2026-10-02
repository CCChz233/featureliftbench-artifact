
from featurelifted import discover_paths, parse_spec


def test_discover_paths_by_glob():
    constraint, globs = parse_spec("/usr/bin/python*")
    assert constraint is None
    candidates = discover_paths(["/usr/bin/python3.11", "/usr/bin/node"], "/usr/bin/python*")
    assert candidates == ["/usr/bin/python3.11"]
