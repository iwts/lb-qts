#!/usr/bin/env python3
"""Validate structured worker JSON results and key artifact invariants."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = {"symbol", "status", "phase", "output_files", "summary", "metrics", "warnings"}
PHASE1_CORE_PHASES = {"fundamental", "strategy", "reasoning", "execution", "review"}
ALLOWED_STATUS = {"ok", "degraded", "failed"}
ALLOWED_PHASE = {"data", "fundamental", "strategy", "reasoning", "execution", "review", "youtube"}
ALLOWED_DIRECTION = {"long", "short", "neutral", ""}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def validate_worker_result(
    result: dict[str, Any],
    *,
    project_root: Path | str | None = None,
    check_files: bool = True,
) -> list[str]:
    errors: list[str] = []
    root = Path(project_root) if project_root is not None else PROJECT_ROOT

    missing = sorted(REQUIRED_TOP_LEVEL - set(result))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
        return errors

    phase = result.get("phase")
    status = result.get("status")
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}

    if status not in ALLOWED_STATUS:
        errors.append(f"status must be one of {sorted(ALLOWED_STATUS)}")
    if phase not in ALLOWED_PHASE:
        errors.append(f"phase must be one of {sorted(ALLOWED_PHASE)}")
    if not isinstance(result.get("output_files"), list):
        errors.append("output_files must be a list")
    if not isinstance(result.get("warnings"), list):
        errors.append("warnings must be a list")
    if not isinstance(result.get("metrics"), dict):
        errors.append("metrics must be an object")
    if phase in PHASE1_CORE_PHASES:
        errors.extend(_validate_phase1_contract(result, metrics))

    if check_files and isinstance(result.get("output_files"), list):
        errors.extend(_validate_output_files(root, result["output_files"]))

    if phase == "reasoning":
        errors.extend(_validate_reasoning(metrics))
    elif phase == "execution":
        errors.extend(_validate_execution(metrics))
        if check_files and isinstance(result.get("output_files"), list):
            errors.extend(_validate_execution_report_content(root, result["output_files"]))

    return errors


def _validate_phase1_contract(result: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(result.get("skills_used"), list):
        errors.append("skills_used must be a list")
    elif not result["skills_used"]:
        errors.append("skills_used must not be empty for Phase 1 core workers")
    if not isinstance(result.get("skills_skipped"), list):
        errors.append("skills_skipped must be a list")
    if not isinstance(result.get("profile_used"), str) or not result.get("profile_used").strip():
        errors.append("profile_used must be a non-empty string")
    if "rules_applied_count" not in metrics:
        errors.append(f"{result.get('phase')}.rules_applied_count is required")
    if "rules_applied_ids" not in metrics:
        errors.append(f"{result.get('phase')}.rules_applied_ids is required")
    elif not isinstance(metrics.get("rules_applied_ids"), list):
        errors.append(f"{result.get('phase')}.rules_applied_ids must be a list")
    return errors


def _validate_output_files(root: Path, output_files: list[Any]) -> list[str]:
    errors: list[str] = []
    for raw_path in output_files:
        if not isinstance(raw_path, str) or not raw_path.strip():
            errors.append("output_files entries must be non-empty strings")
            continue
        path = root / raw_path
        if not path.exists():
            errors.append(f"output file does not exist: {raw_path}")
        elif path.is_file() and path.stat().st_size == 0:
            errors.append(f"output file is empty: {raw_path}")
    return errors


def _number(metrics: dict[str, Any], key: str, default: float = 0) -> float:
    value = metrics.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _validate_reasoning(metrics: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    direction = metrics.get("direction", "")
    if direction not in ALLOWED_DIRECTION:
        errors.append("reasoning.direction must be long|short|neutral")
    if direction != "neutral":
        if _number(metrics, "trade_plans_count") < 2:
            errors.append("reasoning.trade_plans_count must be >= 2 for non-neutral direction")
        if _number(metrics, "best_rr") < 1.5:
            errors.append("reasoning.best_rr must be >= 1.5 for non-neutral direction")
    if _number(metrics, "numeric_evidence_count") < 6:
        errors.append("reasoning.numeric_evidence_count must be >= 6")
    return errors


def _validate_execution(metrics: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    direction = metrics.get("direction", "")
    if direction not in ALLOWED_DIRECTION:
        errors.append("execution.direction must be long|short|neutral")
    plans_total = _number(metrics, "plans_total")
    plans_passed = _number(metrics, "plans_passed_risk_check")
    if direction != "neutral":
        if plans_total < 2:
            errors.append("execution.plans_total must be >= 2 for non-neutral direction")
        if plans_passed < 1:
            errors.append("execution.plans_passed_risk_check must be >= 1 for non-neutral direction")
        if _number(metrics, "best_rr") < 1.5:
            errors.append("execution.best_rr must be >= 1.5 for non-neutral direction")
    for key in ("feishu_report", "feishu_deduction", "feishu_fundamental"):
        if key in metrics and metrics[key] not in {"ok", "failed", "skipped"}:
            errors.append(f"execution.{key} must be ok|failed|skipped")
    return errors


def _validate_execution_report_content(root: Path, output_files: list[Any]) -> list[str]:
    errors: list[str] = []
    markdown_files = [root / p for p in output_files if isinstance(p, str) and p.endswith(".md")]
    if not markdown_files:
        return errors
    report_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in markdown_files if path.exists()
    )
    if "止损" not in report_text and "stop" not in report_text.lower():
        errors.append("execution report must mention stop/止损")
    if not (("若" in report_text and "则" in report_text) or "if" in report_text.lower()):
        errors.append("execution report must include if-then/若-则 action items")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a worker result JSON file")
    parser.add_argument("result_json", help="worker result JSON path")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--no-check-files", action="store_true")
    args = parser.parse_args()

    result_path = Path(args.result_json)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    errors = validate_worker_result(
        result,
        project_root=Path(args.project_root),
        check_files=not args.no_check_files,
    )
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "ok", "errors": []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
