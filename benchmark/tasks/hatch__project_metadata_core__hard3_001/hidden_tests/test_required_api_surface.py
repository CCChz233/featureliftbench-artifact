"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    normalize_project_metadata,
    select_environment,
    MetadataValidationError,
)


def test_required_api_surface():
    assert callable(normalize_project_metadata)
    assert callable(select_environment)
    assert issubclass(MetadataValidationError, BaseException)
