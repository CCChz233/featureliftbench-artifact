from __future__ import annotations

from pathlib import Path

from featurelifted import EntryPoint, EntryPoints, PathDistribution


def _write_dist_info(root: Path, name: str, version: str, entry_text: str) -> Path:
    dist_info = root / f"{name}-{version}.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(entry_text, encoding="utf-8")
    return dist_info


def test_path_distribution_entry_points(tmp_path: Path) -> None:
    meta = _write_dist_info(
        tmp_path,
        "demo",
        "1.0",
        "[console_scripts]\ndemo = demo.cli:main\n",
    )
    dist = PathDistribution(meta)
    eps = EntryPoints(dist.entry_points)
    assert len(eps.select(group="console_scripts")) == 1
    ep = eps["demo"]
    assert isinstance(ep, EntryPoint)
    assert ep.name == "demo"
    assert ep.value == "demo.cli:main"
