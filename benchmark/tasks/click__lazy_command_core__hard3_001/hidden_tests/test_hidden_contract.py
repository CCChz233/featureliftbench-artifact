
import pytest

from featurelifted import LazyCommandCollection, UsageError


def test_envvar_default_map(monkeypatch):
    monkeypatch.setenv("CLICK_DEFAULTS", '{"echo": {"verbose": true}}')
    from featurelifted import Command

    collection = LazyCommandCollection({"echo": lambda: Command("echo")}, envvar="CLICK_DEFAULTS")
    ctx, command, args = collection.resolve(["echo"])
    assert ctx.default_map["echo"]["verbose"] is True


def test_missing_command_raises():
    collection = LazyCommandCollection({})
    with pytest.raises(UsageError, match="no such command"):
        collection.resolve(["missing"])


def test_command_is_cached():
    calls = []

    def factory():
        calls.append(1)
        from featurelifted import Command

        return Command("demo")

    collection = LazyCommandCollection({"demo": factory})
    collection.get_command("demo")
    collection.get_command("demo")
    assert calls == [1]
