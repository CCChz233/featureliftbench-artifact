from featurelifted import App, Response

def test_static_and_typed_routes():
    app = App("demo")
    @app.route("/hello")
    def hello(): return "hello"
    @app.route("/users/<int:user_id>")
    def user(user_id): return {"id": user_id}, 201
    assert app.dispatch("/hello") == Response("hello", 200)
    assert app.dispatch("/users/7") == Response({"id": 7}, 201)

def test_method_dispatch():
    app = App("demo")
    @app.route("/items", methods=["POST"])
    def create(): return "created", 201, {"X-Mode": "write"}
    assert app.dispatch("/items", "POST").headers["X-Mode"] == "write"
    assert app.dispatch("/items", "GET").status_code == 405
