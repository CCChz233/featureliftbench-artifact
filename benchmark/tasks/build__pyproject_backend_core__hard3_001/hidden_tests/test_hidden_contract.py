
import pytest

from featurelifted import BuildSystemTableValidationError, parse_build_system_table, validate_source_directory


def test_unknown_build_system_property():
    with pytest.raises(BuildSystemTableValidationError, match="Unknown properties"):
        parse_build_system_table({"build-system": {"requires": ["setuptools"], "foo": 1}})


def test_validate_source_directory_requires_project_file(tmp_path):
  from featurelifted import BuildException

  with pytest.raises(BuildException, match="does not appear to be a Python project"):
      validate_source_directory(str(tmp_path))
