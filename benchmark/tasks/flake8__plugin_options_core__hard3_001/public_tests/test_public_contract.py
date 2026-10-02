
from featurelifted import OptionManager, PluginSpec, OptionSpec, classify_plugins


def test_option_manager_registers_plugin_options():
    manager = OptionManager()
    plugin = PluginSpec("p", ["E100"], "logical_line", [OptionSpec("max_line_length", parse_from_config=True, default=79)])
    manager.register_options(plugin)
    assert manager.options["max_line_length"].default == 79


def test_classify_plugins_groups_checkers():
    plugins = classify_plugins([
        PluginSpec("tree", ["E1"], "tree"),
        PluginSpec("logical", ["E2"], "logical_line"),
    ])
    assert len(plugins.checkers.tree) == 1
    assert len(plugins.checkers.logical_line) == 1
