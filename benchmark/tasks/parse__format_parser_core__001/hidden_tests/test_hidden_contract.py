from featurelifted import parse

def test_full_match_and_case_policy():
    assert parse("Hello {name}", "hello Ada").named["name"] == "Ada"
    assert parse("Hello {name}", "hello Ada", case_sensitive=True) is None
    assert parse("x={:d}", "prefix x=1") is None

def test_word_and_default_boundaries():
    result = parse("{first:w}-{second}", "alpha-rest-of-value")
    assert result.named == {"first": "alpha", "second": "rest-of-value"}
