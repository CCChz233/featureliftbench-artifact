from featurelifted import App, Response

def test_string_converter_and_response_passthrough():
    app = App("demo")
    @app.route("/greet/<name>")
    def greet(name): return Response(name.upper(), 202, {"X": "1"})
    assert app.dispatch("/greet/ada") == Response("ADA", 202, {"X": "1"})

def test_error_handlers():
    app = App("demo")
    @app.errorhandler(404)
    def missing(code): return f"missing:{code}", 418
    assert app.dispatch("/unknown") == Response("missing:404", 418)
