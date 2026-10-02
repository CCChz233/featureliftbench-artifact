from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_go_gate_report():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_go_gate_report.py"
    spec = importlib.util.spec_from_file_location("generate_go_gate_report", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_flash_oracle_footprint_is_calibration() -> None:
    gate = _load_go_gate_report()

    readiness = gate._readiness_classification(
        mechanical_pass=True,
        flash_tier="B",
        flash_hidden=True,
        flash_ext=0.574468,
        oracle_ext=0.574468,
        copy_ext=1.0,
    )

    assert readiness["readiness"] == "calibration_pass"
    assert readiness["flash_oracle_delta"] == 0.0


def test_flash_hidden_fail_is_hard_discriminative() -> None:
    gate = _load_go_gate_report()

    readiness = gate._readiness_classification(
        mechanical_pass=True,
        flash_tier="A",
        flash_hidden=False,
        flash_ext=0.09,
        oracle_ext=0.45,
        copy_ext=1.0,
    )

    assert readiness["readiness"] == "paper_ready_hard"


def test_flash_hidden_pass_near_copy_all_is_calibration() -> None:
    gate = _load_go_gate_report()

    readiness = gate._readiness_classification(
        mechanical_pass=True,
        flash_tier="B",
        flash_hidden=True,
        flash_ext=0.92,
        oracle_ext=0.45,
        copy_ext=1.0,
    )

    assert readiness["readiness"] == "overextract_pass"
    assert readiness["flash_copy_delta"] == 0.08


def test_flash_hidden_pass_compact_non_oracle_is_hard() -> None:
    gate = _load_go_gate_report()

    readiness = gate._readiness_classification(
        mechanical_pass=True,
        flash_tier="B",
        flash_hidden=True,
        flash_ext=0.55,
        oracle_ext=0.45,
        copy_ext=1.0,
    )

    assert readiness["readiness"] == "paper_ready_hard"


def test_flash_payload_loads_evaluator_result_json(tmp_path: Path) -> None:
    gate = _load_go_gate_report()
    result = {
        "scores": {"functional_gate": 1.0, "extraction_ratio": 0.5},
        "hidden_tests": {"passed": True},
    }
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    payload = gate._flash_eval_payload({"evaluation": {"result_json": str(result_path)}})

    assert payload == result
