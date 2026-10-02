from __future__ import annotations

import json
from pathlib import Path

from harness.featureliftbench.compactness import analyze_submission_footprint
from harness.featureliftbench.scoring import score_submission


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_compactness_vector_does_not_invent_excess_copy_without_complete_gold(tmp_path: Path) -> None:
    task = tmp_path / "benchmark/tasks/demo"
    submission = tmp_path / "benchmark/submissions/demo/candidate"
    reference = tmp_path / "benchmark/submissions/demo/oracle"
    metadata = {
        "source": {"name": "upstream"},
        "environment": {"allowed_dependencies": []},
    }
    _write(task / "metadata.json", json.dumps(metadata))
    _write(task / "repo/upstream/core.py", "def f(x):\n    y = x + 1\n    return y\n")
    _write(submission / "featurelifted/core.py", "def f(x):\n    y = x + 1\n    return y\n")
    _write(reference / "featurelifted/core.py", "def f(x):\n    y = x + 1\n    return y\n")

    metrics = analyze_submission_footprint(
        task, submission, reference_path=reference, functional_pass=True
    )

    assert metrics["copied_loc"] == 3
    assert metrics["excess_copied_loc"] is None
    assert metrics["closure_gold_file_completeness"] == "unresolved"
    assert metrics["compactness_class"] == "copy_heavy_pass"


def test_compactness_detects_unapproved_external_import(tmp_path: Path) -> None:
    task = tmp_path / "benchmark/tasks/demo"
    submission = tmp_path / "benchmark/submissions/demo/candidate"
    reference = tmp_path / "benchmark/submissions/demo/oracle"
    metadata = {
        "source": {"name": "upstream"},
        "environment": {"allowed_dependencies": ["approved-lib"]},
    }
    _write(task / "metadata.json", json.dumps(metadata))
    _write(task / "repo/upstream/core.py", "VALUE = 1\n")
    _write(submission / "featurelifted/core.py", "import requests\nimport approved_lib\n")
    _write(reference / "featurelifted/core.py", "VALUE = 1\n")

    metrics = analyze_submission_footprint(
        task, submission, reference_path=reference, functional_pass=False
    )

    assert metrics["external_dependencies"] == ["approved_lib", "requests"]
    assert metrics["unapproved_external_dependencies"] == ["requests"]
    assert metrics["compactness_class"] == "non_functional"


def test_copy_all_can_pass_functionally_but_scores_poorly_on_compactness() -> None:
    scores = score_submission(
        metrics={"loc": 10_000, "reference_loc": 100},
        metadata={},
        functional_gate_score=1.0,
    )

    assert scores["functional_gate"] == 1.0
    assert scores["final_score"] == 1.0
    assert scores["reference_relative_loc_ratio"] == 100.0
    assert scores["compactness_score"] == 0.01


def test_compactness_uses_frozen_registry_when_oracle_code_is_absent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    task = tmp_path / "benchmark/tasks/demo"
    submission = tmp_path / "benchmark/submissions/demo/candidate"
    registry = tmp_path / "compactness.json"
    _write(
        task / "metadata.json",
        json.dumps(
            {
                "source": {"name": "upstream"},
                "environment": {"allowed_dependencies": []},
            }
        ),
    )
    _write(task / "repo/upstream/core.py", "VALUE = 1\n")
    _write(submission / "featurelifted/core.py", "VALUE = 1\nVALUE_2 = 2\n")
    _write(
        registry,
        json.dumps(
            {
                "task_count": 1,
                "tasks": {"demo": {"python_loc": 1, "file_count": 1}},
            }
        ),
    )
    monkeypatch.setenv("FEATURELIFTBENCH_REFERENCE_REGISTRY", str(registry))

    metrics = analyze_submission_footprint(
        task,
        submission,
        functional_pass=True,
    )

    assert metrics["reference_loc"] == 1
    assert metrics["reference_file_count"] == 1
    assert metrics["extraction_ratio_to_reference"] == 2.0


def test_compactness_stage_never_executes_submission(tmp_path: Path) -> None:
    task = tmp_path / "benchmark/tasks/demo"
    submission = tmp_path / "benchmark/submissions/demo/candidate"
    reference = tmp_path / "benchmark/submissions/demo/oracle"
    marker = tmp_path / "submission-executed"
    _write(
        task / "metadata.json",
        json.dumps(
            {
                "source": {"name": "upstream"},
                "environment": {"allowed_dependencies": []},
            }
        ),
    )
    _write(task / "repo/upstream/core.py", "VALUE = 1\n")
    _write(
        submission / "featurelifted/__init__.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n",
    )
    _write(reference / "featurelifted/__init__.py", "VALUE = 1\n")

    metrics = analyze_submission_footprint(
        task,
        submission,
        reference_path=reference,
        functional_pass=True,
    )

    assert metrics["reference_loc"] == 1
    assert metrics["submitted_file_count"] == 1
    assert not marker.exists()
