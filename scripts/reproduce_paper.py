#!/usr/bin/env python3
"""Check published full-source pass counts."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "deepseek-v4-pro": 115,
    "deepseek-v4-flash": 108,
    "gpt-5.6-luna": 102,
    "openai/claude-sonnet-5": 89,
    "glm-5.3-flash": 68,
    "qwen3.6-35b-a3b-fp8": 63,
    "gpt-oss-120b": 36,
}

def main() -> None:
    path = ROOT / "results" / "main_results.csv"
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    pairs = {(row["configuration"], row["task_id"]) for row in rows}
    if len(rows) != 1050 or len(pairs) != 1050:
        raise SystemExit(f"expected 1050 outcomes, found {len(rows)}")
    counts = {model: 0 for model in EXPECTED}
    for row in rows:
        if row["pass"] == "true":
            counts[row["configuration"]] += 1
    for model, expected in EXPECTED.items():
        print(f"{model}: {counts[model]}/150")
        if counts[model] != expected:
            raise SystemExit(f"{model}: {counts[model]} != {expected}")
    print("1050 outcomes checked.")

if __name__ == "__main__":
    main()
