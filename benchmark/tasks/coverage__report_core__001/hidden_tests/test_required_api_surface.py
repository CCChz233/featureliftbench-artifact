"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    Analysis,
    CoverageConfig,
    XmlReporter,
    rate,
    serialize_xml,
)


def test_required_api_surface():
    assert isinstance(Analysis, type)
    assert isinstance(CoverageConfig, type)
    assert CoverageConfig is not None
    assert CoverageConfig is not None
    assert isinstance(XmlReporter, type)
    assert XmlReporter is not None
    assert XmlReporter is not None
    assert hasattr(XmlReporter, 'xml_file')
    assert XmlReporter is not None
    assert callable(rate)
    assert callable(serialize_xml)
