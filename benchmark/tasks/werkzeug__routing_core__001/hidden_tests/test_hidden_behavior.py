from __future__ import annotations

import pytest

from featurelifted.routing import Map, Rule, Subdomain, Submount
from featurelifted.routing.exceptions import RequestRedirect


def test_subdomain_and_submount_routing() -> None:
    mapping = Map(
        [
            Subdomain(
                "api",
                [Rule("/v1/status", endpoint="api_status")],
            ),
            Submount(
                "/blog",
                [Rule("/", endpoint="blog_index"), Rule("/<slug>", endpoint="blog_post")],
            ),
        ],
        default_subdomain="www",
    )
    api = mapping.bind("example.com", subdomain="api")
    assert api.match("/v1/status") == ("api_status", {})

    www = mapping.bind("example.com")
    assert www.match("/blog/") == ("blog_index", {})
    assert www.match("/blog/hello-world") == ("blog_post", {"slug": "hello-world"})


def test_strict_slashes_redirect() -> None:
    mapping = Map([Rule("/about/", endpoint="about", strict_slashes=True)])
    adapter = mapping.bind("example.com")
    with pytest.raises(RequestRedirect) as exc:
        adapter.match("/about")
    assert exc.value.new_url.endswith("/about/")
