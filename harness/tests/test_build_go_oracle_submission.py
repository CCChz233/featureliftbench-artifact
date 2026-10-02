from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_builder():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_go_oracle_submission.py"
    spec = importlib.util.spec_from_file_location("build_go_oracle_submission", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_go_oracle_excludes_non_target_files(tmp_path, monkeypatch):
    builder = _load_builder()
    monkeypatch.setattr(builder, "SUBMISSIONS_DIR", tmp_path / "submissions")
    task = _make_task(tmp_path, "semver__version_parse_core__001")
    (task / "repo" / "version.go").write_text("package semver\n\nfunc Parse() {}\n", encoding="utf-8")
    (task / "repo" / "bulk_excluded.go").write_text(
        "package semver\n\nfunc Excluded() {}\n",
        encoding="utf-8",
    )

    out = builder.build_go_submission(task, variant="oracle")

    assert (out / "version.go").read_text(encoding="utf-8").startswith("package featurelifted")
    assert not (out / "bulk_excluded.go").exists()
    assert (out / "go.mod").read_text(encoding="utf-8").startswith("module featurelifted\n")


def test_build_go_naive_submission(tmp_path, monkeypatch):
    builder = _load_builder()
    monkeypatch.setattr(builder, "SUBMISSIONS_DIR", tmp_path / "submissions")
    task = _make_task(tmp_path, "humanize__bytes_format_core__001")

    out = builder.build_go_submission(task, variant="naive")

    assert (out / "humanize.go").is_file()
    text = (out / "humanize.go").read_text(encoding="utf-8")
    assert "func Bytes" in text
    assert "func ParseBytes" in text
    assert (out / "go.mod").read_text(encoding="utf-8").startswith("module featurelifted\n")


def _make_task(root: Path, task_id: str) -> Path:
    task = root / task_id
    (task / "repo").mkdir(parents=True)
    metadata = {
        "task_id": task_id,
        "environment": {
            "module_path": "featurelifted",
        },
    }
    (task / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return task
