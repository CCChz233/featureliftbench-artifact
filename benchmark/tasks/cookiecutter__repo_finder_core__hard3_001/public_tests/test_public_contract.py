
from featurelifted import RepoFinder


def test_find_template_with_abbreviation():
    finder = RepoFinder(abbreviations={"gh": "https://github.com/{0}/{1}.git"})
    result = finder.find_template("gh:org/template")
    assert result["expanded"] == "https://github.com/org/template.git"
    assert "org/template" in result["local_path"]
