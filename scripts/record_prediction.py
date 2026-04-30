#!/usr/bin/env python3
"""Append structured execution predictions for later review/backtesting."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS_CSV = PROJECT_ROOT / "data" / "performance" / "predictions.csv"
PREDICTION_FIELDS = [
    "symbol",
    "report_date",
    "direction",
    "rating",
    "regime",
    "entry_type",
    "entry",
    "stop",
    "target_1",
    "target_2",
    "rr",
    "rules_applied",
    "report_file",
    "deduction_file",
]


def append_prediction(csv_path: Path | str, prediction: dict[str, Any]) -> Path:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {field: _stringify(prediction.get(field, "")) for field in PREDICTION_FIELDS}
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PREDICTION_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)
    return path


def prediction_from_execution_summary(
    summary: dict[str, Any],
    *,
    report_date: str | None = None,
) -> dict[str, str]:
    metrics = summary.get("metrics", {}) if isinstance(summary.get("metrics"), dict) else {}
    plans = summary.get("plans", []) if isinstance(summary.get("plans"), list) else []
    primary_plan = _first_non_neutral_plan(plans)
    output_files = summary.get("output_files", []) if isinstance(summary.get("output_files"), list) else []
    source_files = summary.get("source_files", {}) if isinstance(summary.get("source_files"), dict) else {}
    rules = metrics.get("rules_applied_ids", [])

    return {
        "symbol": _stringify(summary.get("symbol", "")),
        "report_date": report_date or date.today().isoformat(),
        "direction": _stringify(metrics.get("direction", primary_plan.get("direction", ""))),
        "rating": _stringify(metrics.get("rating", "")),
        "regime": _stringify(metrics.get("regime", "")),
        "entry_type": _stringify(primary_plan.get("entry_type", "")),
        "entry": _stringify(primary_plan.get("entry", primary_plan.get("entry_price", ""))),
        "stop": _stringify(primary_plan.get("stop", primary_plan.get("stop_loss", ""))),
        "target_1": _stringify(primary_plan.get("target_1", "")),
        "target_2": _stringify(primary_plan.get("target_2", "")),
        "rr": _stringify(primary_plan.get("rr", metrics.get("best_rr", ""))),
        "rules_applied": ";".join(_stringify(rule) for rule in rules),
        "report_file": _stringify(output_files[0] if output_files else ""),
        "deduction_file": _stringify(source_files.get("deduction", "")),
    }


def _first_non_neutral_plan(plans: list[Any]) -> dict[str, Any]:
    for plan in plans:
        if isinstance(plan, dict) and plan.get("direction") != "neutral":
            return plan
    for plan in plans:
        if isinstance(plan, dict):
            return plan
    return {}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one execution summary to predictions.csv")
    parser.add_argument("execution_summary_json", help="structured execution summary JSON")
    parser.add_argument("--output", default=str(DEFAULT_PREDICTIONS_CSV))
    parser.add_argument("--report-date", default=None)
    args = parser.parse_args()

    summary = json.loads(Path(args.execution_summary_json).read_text(encoding="utf-8"))
    prediction = prediction_from_execution_summary(summary, report_date=args.report_date)
    output = append_prediction(Path(args.output), prediction)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
