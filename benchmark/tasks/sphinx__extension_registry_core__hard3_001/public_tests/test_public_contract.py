
from featurelifted import ComponentRegistry, ExtensionMetadata


def test_load_extension_registers_metadata():
    registry = ComponentRegistry()

    def setup(app):
        app.add_directive("demo", object)
        return ExtensionMetadata(version="1.2", parallel_read_safe=False)

    metadata = registry.load_extension("demo", setup)
    assert metadata.version == "1.2"
    assert "demo" in registry.directives
