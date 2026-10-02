from featurelifted import compile, parse

def test_named_and_typed_fields():
    result = parse("user={name:w} age={age:d}", "user=Ada age=37")
    assert result.named == {"name": "Ada", "age": 37}
    assert result.fixed == ()

def test_positional_and_escaped_braces():
    parser = compile("point={{x={:d}, y={:f}}}")
    result = parser.parse("point={x=3, y=2.5}")
    assert result.fixed == (3, 2.5)
