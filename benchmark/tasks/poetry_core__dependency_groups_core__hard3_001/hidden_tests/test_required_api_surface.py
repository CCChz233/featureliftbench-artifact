"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    parse_project_dependencies,
    resolve_group,
    DependencyGroup,
    DependencySpec,
)


def test_required_api_surface():
    assert callable(parse_project_dependencies)
    assert callable(resolve_group)
    assert isinstance(DependencyGroup, type)
    assert isinstance(DependencySpec, type)
