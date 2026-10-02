"""Deterministic scoring for construction-labeled canary audits."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .canaries import CANARY_CLASSES


def score_canary_records(
    manifest: Mapping[str, Any],
    records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected = {
        str(row["case_id"]): str(row["expected_verdict"])
        for row in manifest.get("cases") or []
        if isinstance(row, Mapping) and row.get("case_id")
    }
    confusion: dict[str, Counter[str]] = {
        label: Counter() for label in CANARY_CLASSES
    }
    missing: list[str] = []
    correct = 0
    abstained = 0
    for case_id, truth in expected.items():
        record = records.get(case_id)
        if record is None:
            missing.append(case_id)
            prediction = "missing"
        else:
            prediction = str(record.get("verdict") or "missing")
        confusion[truth][prediction] += 1
        if prediction == truth:
            correct += 1
        if prediction == "abstain":
            abstained += 1

    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for label in CANARY_CLASSES:
        true_positive = confusion[label][label]
        false_negative = sum(confusion[label].values()) - true_positive
        false_positive = sum(
            confusion[other][label]
            for other in CANARY_CLASSES
            if other != label
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        f1_values.append(f1)
        per_class[label] = {
            "support": sum(confusion[label].values()),
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        }
    total = len(expected)
    return {
        "schema_version": "featureliftbench.agentic_evidence.calibration.v1",
        "case_count": total,
        "record_count": len(records),
        "correct": correct,
        "accuracy": round(correct / total, 6) if total else 0.0,
        "macro_f1": round(sum(f1_values) / len(f1_values), 6),
        "abstain_count": abstained,
        "abstain_rate": round(abstained / total, 6) if total else 0.0,
        "missing_case_ids": sorted(missing),
        "per_class": per_class,
        "confusion": {
            truth: dict(sorted(counts.items()))
            for truth, counts in confusion.items()
        },
    }


def load_record_directory(root: str | Path) -> dict[str, dict[str, Any]]:
    base = Path(root)
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(base.glob("*/audit_record.json")):
        validation_path = path.parent / "validation.json"
        try:
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records[path.parent.name] = payload
    return records
