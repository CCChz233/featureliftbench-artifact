from __future__ import annotations

from featurelifted import format


def test_format_supports_common_options() -> None:
    formatted = format(
        "select a,b from t where a=1 and b=2",
        keyword_case="upper",
        reindent=True,
        use_space_around_operators=True,
    )

    assert formatted == "SELECT a,\n       b\nFROM t\nWHERE a = 1\n  AND b = 2"
