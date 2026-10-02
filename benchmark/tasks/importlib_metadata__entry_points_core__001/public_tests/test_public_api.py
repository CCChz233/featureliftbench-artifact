from __future__ import annotations

from featurelifted import EntryPoint, EntryPoints, Sectioned


def test_entry_point_value_parsing_and_selection() -> None:
    ep = EntryPoint(name="console", value="pkg.mod:main", group="console_scripts")
    assert ep.module == "pkg.mod"
    assert ep.attr == "main"
    selected = EntryPoints((ep,)).select(group="console_scripts", name="console")
    assert len(selected) == 1
    assert selected["console"].matches(name="console", group="console_scripts")


def test_sectioned_entry_point_config() -> None:
    sample = """
    [console_scripts]
    tool = pkg.tool:run
    """
    pairs = list(Sectioned.section_pairs(sample))
    assert pairs[0].name == "console_scripts"
    assert pairs[0].value.name == "tool"
    assert pairs[0].value.value == "pkg.tool:run"
