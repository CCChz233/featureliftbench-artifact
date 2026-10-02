import pytest
from featurelifted import Choices, Config, RepositoryEnv

def test_env_file_quotes_comments_and_empty(tmp_path):
    path = tmp_path / ".env"
    path.write_text("NAME='Ada Lovelace' # note\nEMPTY=\nFLAG=YES\n", encoding="utf-8")
    config = Config(RepositoryEnv(path), environ={})
    assert config("NAME") == "Ada Lovelace"
    assert config("EMPTY") == ""
    assert config("FLAG", cast=bool) is True

def test_choices_and_float():
    config = Config(type("R", (), {"data": {"MODE": "prod", "RATE": "1.25"}, "__contains__": lambda s,k:k in s.data, "__getitem__": lambda s,k:s.data[k]})(), environ={})
    assert config("MODE", cast=Choices(["dev", "prod"])) == "prod"
    assert config("RATE", cast=float) == 1.25
    with pytest.raises(ValueError): Choices(["dev"])("prod")
