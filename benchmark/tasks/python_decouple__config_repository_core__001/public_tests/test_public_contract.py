import pytest
from featurelifted import Config, Csv, RepositoryDict, UndefinedValueError

def test_precedence_defaults_and_casts():
    config = Config(RepositoryDict({"PORT": "8000", "DEBUG": "no"}), environ={"PORT": "9000"})
    assert config("PORT", cast=int) == 9000
    assert config("DEBUG", cast=bool) is False
    assert config("MISSING", default="x") == "x"
    with pytest.raises(UndefinedValueError): config("REQUIRED")

def test_csv_cast():
    config = Config(RepositoryDict({"HOSTS": "a, b,c"}), environ={})
    assert config("HOSTS", cast=Csv()) == ["a", "b", "c"]
