
from featurelifted import PluginSpec, apply_select_ignore, classify_plugins


def test_select_and_ignore_precedence():
    plugins = classify_plugins([
        PluginSpec("a", ["E100", "W100"], "logical_line"),
        PluginSpec("b", ["F401"], "tree"),
    ])
    selected = apply_select_ignore(plugins, select={"E100"}, ignore={"W100"})
    assert [p.plugin.name for p in selected.checkers.logical_line] == ["a"]
    ignored = apply_select_ignore(plugins, select=set(), ignore={"F"})
    assert [p.plugin.name for p in ignored.checkers.tree] == []
