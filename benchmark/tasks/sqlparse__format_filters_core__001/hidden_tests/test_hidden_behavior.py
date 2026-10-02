from __future__ import annotations

import pytest

from featurelifted import format
from featurelifted.exceptions import SQLParseError


def test_formatter_comment_stripping_and_spacing() -> None:
    assert (
        format(
            "select a, -- inline\n b from t",
            strip_comments=True,
            reindent=True,
            keyword_case="upper",
        )
        == "SELECT a, b\nFROM t"
    )

    assert (
        format("select a+b as total from t", use_space_around_operators=True)
        == "select a + b as total from t"
    )


def test_formatter_rejects_invalid_options() -> None:
    with pytest.raises(SQLParseError, match="Invalid value for keyword_case"):
        format("select 1", keyword_case="invalid")
