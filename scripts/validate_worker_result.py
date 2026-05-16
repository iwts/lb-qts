#!/usr/bin/env python3
"""Validate structured worker JSON results and key artifact invariants."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = {"symbol", "status", "phase", "output_files", "summary", "metrics", "warnings"}
PHASE1_CORE_PHASES = {"fundamental", "strategy", "reasoning", "execution", "review"}
PROFILE_AWARE_PHASES = {"reasoning", "execution"}
ALLOWED_STATUS = {"ok", "degraded", "failed"}
ALLOWED_PHASE = {"data", "fundamental", "strategy", "reasoning", "execution", "review", "youtube"}
ALLOWED_DIRECTION = {"long", "short", "neutral", ""}
ALLOWED_PROFILE_SOURCE = {"manual", "rule", "default"}
ALLOWED_PROFILE_RISK = {"low", "medium", "high"}
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
        errors.extend(_validate_phase1_contract(result, metrics, root=root, check_files=check_files))

    if check_files and isinstance(result.get("output_files"), list):
        errors.extend(_validate_output_files(root, result["output_files"]))

    if phase == "reasoning":
        errors.extend(_validate_reasoning(metrics))
    elif phase == "execution":
        errors.extend(_validate_execution(metrics))
        if check_files and isinstance(result.get("output_files"), list):
            errors.extend(_validate_execution_report_content(root, result["output_files"]))
    if phase in PROFILE_AWARE_PHASES and check_files and isinstance(result.get("output_files"), list):
        errors.extend(_validate_profile_report_content(root, result["output_files"]))

    return errors


def _validate_phase1_contract(
    result: dict[str, Any],
    metrics: dict[str, Any],
    *,
    root: Path,
    check_files: bool,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(result.get("skills_used"), list):
        errors.append("skills_used must be a list")
    elif not result["skills_used"]:
        errors.append("skills_used must not be empty for Phase 1 core workers")
    if not isinstance(result.get("skills_skipped"), list):
        errors.append("skills_skipped must be a list")
    if not isinstance(result.get("profile_used"), str) or not result.get("profile_used").strip():
        errors.append("profile_used must be a non-empty string")
    if result.get("phase") in PROFILE_AWARE_PHASES:
        errors.extend(_validate_profile_contract(result, root=root, check_files=check_files))
    if "rules_applied_count" not in metrics:
        errors.append(f"{result.get('phase')}.rules_applied_count is required")
    if "rules_applied_ids" not in metrics:
        errors.append(f"{result.get('phase')}.rules_applied_ids is required")
    elif not isinstance(metrics.get("rules_applied_ids"), list):
        errors.append(f"{result.get('phase')}.rules_applied_ids must be a list")
    return errors


def _validate_profile_contract(result: dict[str, Any], *, root: Path, check_files: bool) -> list[str]:
    errors: list[str] = []
    status = result.get("status")
    profile_used = result.get("profile_used")
    optional_profiles = result.get("optional_profiles")
    profile_file_paths = result.get("profile_file_paths")
    profile_source = result.get("profile_source")
    profile_effect = result.get("profile_effect")

    if not isinstance(optional_profiles, list):
        errors.append("optional_profiles must be a list for profile-aware phases")
        optional_profiles = []
    elif len(optional_profiles) > 2:
        errors.append("optional_profiles must contain at most 2 profiles")

    if profile_source not in ALLOWED_PROFILE_SOURCE:
        errors.append(f"profile_source must be one of {sorted(ALLOWED_PROFILE_SOURCE)}")

    if not isinstance(profile_file_paths, list):
        errors.append("profile_file_paths must be a list for profile-aware phases")
        profile_file_paths = []

    if profile_used == "default" and status == "ok":
        errors.append("default profile requires degraded or failed status for profile-aware phases")
    if profile_used == "default" and profile_file_paths:
        errors.append("default profile must not include profile_file_paths")
    if profile_used != "default" and profile_source == "default":
        errors.append("non-default profile must not use default profile_source")
    if profile_used != "default" and not profile_file_paths:
        errors.append("profile_file_paths must include the primary profile file")
    if isinstance(profile_used, str) and profile_used in optional_profiles:
        errors.append("optional_profiles must not include the primary profile")
    string_profile_paths = [raw_path for raw_path in profile_file_paths if isinstance(raw_path, str)]
    if len(string_profile_paths) != len(set(string_profile_paths)):
        errors.append("profile_file_paths must not contain duplicates")

    for index, raw_path in enumerate(profile_file_paths):
        if not isinstance(raw_path, str) or not raw_path.strip():
            errors.append(f"profile_file_paths[{index}] must be a non-empty string")
            continue
        path = root / raw_path
        try:
            relative_path = path.resolve().relative_to(root.resolve())
        except ValueError:
            errors.append(f"profile_file_paths[{index}] must stay within the project: {raw_path}")
            continue
        if len(relative_path.parts) < 3 or relative_path.parts[0:2] != ("agents", "profiles"):
            errors.append(f"profile_file_paths[{index}] must be under agents/profiles: {raw_path}")
            continue
        if check_files:
            if not path.exists():
                errors.append(f"profile file does not exist: {raw_path}")
            elif path.stat().st_size == 0:
                errors.append(f"profile file is empty: {raw_path}")

    if isinstance(profile_used, str) and profile_used != "default":
        expected_primary = f"agents/profiles/{profile_used}.md"
        if expected_primary not in profile_file_paths:
            errors.append(f"profile_file_paths must include primary profile: {expected_primary}")
    for profile_name in optional_profiles:
        if not isinstance(profile_name, str) or not profile_name.strip():
            errors.append("optional_profiles entries must be non-empty strings")
            continue
        expected_overlay = f"agents/profiles/{profile_name}.md"
        if expected_overlay not in profile_file_paths:
            errors.append(f"profile_file_paths must include optional profile: {expected_overlay}")

    if not isinstance(profile_effect, dict):
        errors.append("profile_effect must be an object for profile-aware phases")
        return errors

    weight_bias = profile_effect.get("weight_bias_applied")
    no_weight_reason = profile_effect.get("no_weight_difference_reason")
    if not isinstance(weight_bias, dict):
        errors.append("profile_effect.weight_bias_applied must be an object")
    elif not weight_bias and not (isinstance(no_weight_reason, str) and no_weight_reason.strip()):
        errors.append("profile_effect must describe weight_bias_applied or no_weight_difference_reason")

    if not isinstance(profile_effect.get("hard_concerns_triggered"), list):
        errors.append("profile_effect.hard_concerns_triggered must be a list")
    if not isinstance(profile_effect.get("preferred_setups_considered"), list):
        errors.append("profile_effect.preferred_setups_considered must be a list")

    profile_risk = profile_effect.get("profile_not_applicable_risk")
    if profile_risk not in ALLOWED_PROFILE_RISK:
        errors.append(f"profile_effect.profile_not_applicable_risk must be one of {sorted(ALLOWED_PROFILE_RISK)}")
    elif profile_risk in {"medium", "high"} and status == "ok":
        errors.append("profile_not_applicable_risk medium/high requires degraded or failed status")
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


def _validate_profile_report_content(root: Path, output_files: list[Any]) -> list[str]:
    errors: list[str] = []
    markdown_files = [root / p for p in output_files if isinstance(p, str) and p.endswith(".md")]
    if not markdown_files:
        return errors
    report_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in markdown_files if path.exists()
    )
    lower_text = report_text.lower()
    if "profile" not in lower_text:
        errors.append("profile-aware report must include a Profile section")
    if "权重" not in report_text and "weight" not in lower_text:
        errors.append("profile-aware report must describe profile weight impact")
    if "hard concern" not in lower_text and "hard concerns" not in lower_text:
        errors.append("profile-aware report must describe profile hard concerns")
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
