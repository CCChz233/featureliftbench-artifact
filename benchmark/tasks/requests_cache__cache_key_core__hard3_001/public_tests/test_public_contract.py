from featurelifted import CachePolicy, create_cache_key, create_key


class Request:
    method = "GET"
    url = "https://example.test/items?b=2&a=1"
    headers = {"Accept": "application/json"}
    body = None


def test_query_order_normalized():
    assert create_key("GET", "https://example.test/items?b=2&a=1") == create_key(
        "GET", "https://example.test/items?a=1&b=2"
    )
    assert create_cache_key(Request()) == create_key("GET", "https://example.test/items?a=1&b=2", headers=Request.headers)


def test_ignored_parameter_redacts_value_for_matching():
    first = create_key("GET", "https://example.test/items?token=secret&a=1", ignored_parameters=["token"])
    second = create_key("GET", "https://example.test/items?token=other&a=1", ignored_parameters=["token"])
    different = create_key("GET", "https://example.test/items?token=other&a=1")

    assert first == second
    assert first != different


def test_cache_control_max_age_and_no_store():
    assert CachePolicy.from_headers({"Cache-Control": "max-age=60"}).expiration_seconds == 60
    policy = CachePolicy.from_headers({"Cache-Control": "no-store, max-age=60"})
    assert policy.should_store is False
    assert policy.expiration_seconds is None
