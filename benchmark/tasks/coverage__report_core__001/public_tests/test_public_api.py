from __future__ import annotations

import xml.dom.minidom

from featurelifted import rate
from featurelifted import Analysis
from featurelifted import CoverageConfig
from featurelifted import XmlReporter


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


def test_rate_handles_zero_and_fraction() -> None:
    assert rate(0, 0) == "1"
    assert rate(1, 4) == "0.25"


def test_xml_file_emits_line_elements() -> None:
    config = CoverageConfig()
    reporter = XmlReporter(_FakeCoverage(config))
    impl = xml.dom.minidom.getDOMImplementation()
    assert impl is not None
    reporter.xml_out = impl.createDocument(None, "coverage", None)

    analysis = Analysis(
        precision=0,
        filename="/proj/src/pkg/mod.py",
        has_arcs=False,
        statements={1, 2, 3},
        excluded=set(),
        executed={1, 3},
        arc_possibilities_set=set(),
        arcs_executed_set=set(),
        exit_counts={},
        no_branch=set(),
    )
    reporter.xml_file(_FakeFileReporter("/proj/src/pkg/mod.py", "src/pkg/mod.py"), analysis, False)

    package = reporter.packages["src.pkg"]
    assert "src/pkg/mod.py" in package.elements
    xclass = package.elements["src/pkg/mod.py"]
    line_numbers = {
        int(node.getAttribute("number"))
        for node in xclass.getElementsByTagName("line")
    }
    assert line_numbers == {1, 2, 3}
