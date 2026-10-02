
from featurelifted import Match, Mount, Route, Router


def test_mount_prefix_and_url_path_for():
    child = Route("detail", "/{name}", methods=["GET"])
    router = Router([Mount("/api", [child])])
    route, params = router.match("/api/hello")
    assert route.name == "detail"
    assert params == {"name": "hello"}
    assert router.url_path_for("detail", name="hello") == "/api/hello"


def test_method_mismatch_returns_no_match():
    route = Route("x", "/x", methods=["POST"])
    match, params = route.matches("/x", "GET")
    assert match is Match.NONE
    assert params == {}
