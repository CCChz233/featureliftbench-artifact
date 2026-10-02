"""Constitution API-surface coverage generated from public_spec."""

from featurelifted import (
    validate_source_directory,
    parse_build_system_table,
    BuildException,
    BuildSystemTableValidationError,
)


def test_required_api_surface():
    assert callable(validate_source_directory)
    assert callable(parse_build_system_table)
    assert issubclass(BuildException, BaseException)
    assert issubclass(BuildSystemTableValidationError, BaseException)
