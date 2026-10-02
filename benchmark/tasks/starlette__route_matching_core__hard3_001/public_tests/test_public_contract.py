
from featurelifted import Route, Router


def test_router_matches_route():
    router = Router([Route("item", "/items/{item_id:int}")])
    route, params = router.match("/items/42")
    assert route.name == "item"
    assert params == {"item_id": 42}
