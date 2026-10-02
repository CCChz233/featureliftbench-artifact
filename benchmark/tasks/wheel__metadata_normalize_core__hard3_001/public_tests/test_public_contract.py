
from featurelifted import safe_name, safe_extra


def test_safe_name_and_extra():
    assert safe_name("My Project") == "My-Project"
    assert safe_extra("Dev Tools") == "dev_tools"
