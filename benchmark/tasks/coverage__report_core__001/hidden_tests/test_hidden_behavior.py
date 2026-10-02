from __future__ import annotations

import xml.dom.minidom

from featurelifted import Analysis
from featurelifted import CoverageConfig
from featurelifted import XmlReporter
from featurelifted import serialize_xml


class _FakeFileReporter:
    def __init__(self, filename: str, rel: str) -> None:
        self.filename = filename
        self._rel = rel

    def relative_filename(self) -> str:
        return self._rel


class _FakeCoverage:
    def __init__(self, config: CoverageConfig) -> None:
        self.config = config

    def get_data(self):
        return type("Data", (), {"has_arcs": lambda self: False})()


def _analysis(*, statements: set[int], executed: set[int]) -> Analysis:
    return Analysis(
        precision=0,
        filename="/proj/src/deep/nested/mod.py",
        has_arcs=False,
        statements=statements,
        excluded=set(),
        executed=executed,
        arc_possibilities_set=set(),
        arcs_executed_set=set(),
        exit_counts={},
        no_branch=set(),
    )


def test_xml_package_depth_truncates_package_name() -> None:
    config = CoverageConfig()
    config.xml_package_depth = 1
    reporter = XmlReporter(_FakeCoverage(config))
    impl = xml.dom.minidom.getDOMImplementation()
    assert impl is not None
    reporter.xml_out = impl.createDocument(None, "coverage", None)

    reporter.xml_file(
        _FakeFileReporter("/proj/src/deep/nested/mod.py", "src/deep/nested/mod.py"),
        _analysis(statements={1}, executed={1}),
        False,
    )

    assert "src" in reporter.packages
    assert "src.deep" not in reporter.packages


def test_skip_empty_omits_zero_statement_files() -> None:
    config = CoverageConfig()
    config.skip_empty = True
    reporter = XmlReporter(_FakeCoverage(config))
    impl = xml.dom.minidom.getDOMImplementation()
    assert impl is not None
    reporter.xml_out = impl.createDocument(None, "coverage", None)

    reporter.xml_file(
        _FakeFileReporter("/proj/src/empty.py", "src/empty.py"),
        _analysis(statements=set(), executed=set()),
        False,
    )

    assert reporter.packages == {}


def test_serialize_xml_produces_coverage_root() -> None:
    impl = xml.dom.minidom.getDOMImplementation()
    assert impl is not None
    document = impl.createDocument(None, "coverage", None)
    document.documentElement.setAttribute("line-rate", "1")

    xml_text = serialize_xml(document)

    assert xml_text.startswith("<?xml")
    assert "<coverage" in xml_text
    assert 'line-rate="1"' in xml_text
