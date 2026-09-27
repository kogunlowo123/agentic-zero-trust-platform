#!/usr/bin/env python3
"""CI evaluation gate — fails if metrics drop below thresholds."""
from __future__ import annotations
import json
import sys
from pathlib import Path

THRESHOLDS = {
    "recall_at_5": 0.70,
    "mrr": 0.65,
    "faithfulness": 0.80,
    "citation_accuracy": 0.85,
}


def run_ci_gate(results: dict) -> bool:
    failures = []
    for metric, threshold in THRESHOLDS.items():
        actual = results.get(metric)
        if actual is None:
            print(f"  SKIP: {metric} not in results")
            continue
        if actual < threshold:
            failures.append(f"  FAIL: {metric}: {actual:.3f} < {threshold:.3f}")
        else:
            print(f"  PASS: {metric}: {actual:.3f} >= {threshold:.3f}")
    if failures:
        print("\nEVAL GATE FAILED:")
        for f in failures:
            print(f)
        return False
    print("\nAll eval metrics pass CI gate.")
    return True


if __name__ == "__main__":
    results_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("eval_results.json")
    if not results_path.exists():
        print(f"Results file not found: {results_path}")
        sys.exit(1)
    results = json.loads(results_path.read_text())
    success = run_ci_gate(results)
    sys.exit(0 if success else 1)
