
from featurelifted import Command, LazyCommandCollection


def test_lazy_command_invoke():
    def make_echo():
        return Command("echo", callback=lambda ctx, args: args)

    collection = LazyCommandCollection({"echo": make_echo})
    assert collection.invoke(["echo", "hi"]) == ["hi"]
