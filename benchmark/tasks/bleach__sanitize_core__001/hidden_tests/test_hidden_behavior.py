from __future__ import annotations

import re
from pathlib import Path

from featurelifted import clean


def test_strip_disallowed_script() -> None:
    dirty = '<b>keep</b><script>x</script>'
    assert clean(dirty, tags=["b"], strip=True) == "<b>keep</b>x"


def test_strip_mode_removes_tag() -> None:
    dirty = "<b>bold</b> plain"
    assert clean(dirty, tags=[], strip=True) == "bold plain"


def test_javascript_href_stripped() -> None:
    dirty = '<a href="javascript:alert(1)">x</a>'
    assert 'href=' not in clean(dirty)


def test_strip_comments_removed() -> None:
    dirty = "<b>hi</b><!-- secret -->"
    assert clean(dirty, strip_comments=True) == "<b>hi</b>"


def test_custom_attributes_callable() -> None:
    def allow_href(tag: str, name: str, value: str) -> bool:
        return name == "href" and value.startswith("https://")

    dirty = '<a href="https://ok">y</a><a href="http://no">n</a>'
    out = clean(dirty, tags=["a"], attributes={"a": allow_href})
    assert 'href="https://ok"' in out
    assert "http://no" not in out


def test_no_bleach_import_surface() -> None:
    import featurelifted

    pkg_root = Path(featurelifted.__file__).parent
    import_pattern = re.compile(r"^\s*(?:from bleach|import bleach)\b", re.MULTILINE)
    for path in pkg_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text)
