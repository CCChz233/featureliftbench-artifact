from __future__ import annotations

from featurelifted.routing import Map, Rule


def test_match_and_build_simple_rules() -> None:
    mapping = Map(
        [
            Rule("/", endpoint="index"),
            Rule("/users/<int:user_id>", endpoint="user"),
        ]
    )
    adapter = mapping.bind("example.com")
    assert adapter.match("/") == ("index", {})
    assert adapter.match("/users/42") == ("user", {"user_id": 42})
    assert adapter.build("user", {"user_id": 7}) == "/users/7"
